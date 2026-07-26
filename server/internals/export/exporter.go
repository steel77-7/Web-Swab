package export

import (
	"archive/zip"
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"log"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

const ChunkSize = 16 * 1024

type ManifestLink struct {
	TargetURL  string `json:"target_url"`
	TargetFile string `json:"target_file,omitempty"`
	AnchorText string `json:"anchor_text"`
	LinkType   string `json:"link_type"`
}

type ManifestPage struct {
	ID            int            `json:"id"`
	File          string         `json:"file"`
	URL           string         `json:"url"`
	Title         string         `json:"title"`
	Depth         int            `json:"depth"`
	HTTPStatus    int            `json:"http_status"`
	ContentType   string         `json:"content_type"`
	ContentLength int            `json:"content_length"`
	MetadataStr   *string        `json:"metadata_str"`
	OutboundLinks []ManifestLink `json:"outbound_links"`
}

type Manifest struct {
	Version    string         `json:"version"`
	JobID      string         `json:"job_id"`
	ExportedAt string         `json:"exported_at"`
	RootURL    string         `json:"root_url"`
	TotalPages int            `json:"total_pages"`
	Pages      []ManifestPage `json:"pages"`
}

type Exporter struct {
	Pool *pgxpool.Pool
}

func NewExporter(pool *pgxpool.Pool) *Exporter {
	return &Exporter{Pool: pool}
}

type pageData struct {
	urlID         int
	url           string
	depth         int
	title         string
	metadataStr   *string
	htmlSource    *string
	httpStatus    int
	contentType   string
	contentLength int
}

func (e *Exporter) BuildZip(ctx context.Context, jobID string) ([]byte, error) {
	var fetchedPages []pageData
	urlIDToFilePath := make(map[int]string)
	urlStrToFilePath := make(map[string]string)
	urlIDs := make([]int, 0)
	rootURL := "unknown"

	if e != nil && e.Pool != nil {
		rootQuery := `
			SELECT u.url
			FROM job j
			LEFT JOIN url u ON j.url_id = u.id
			WHERE j.job_id = $1
			LIMIT 1;
		`
		_ = e.Pool.QueryRow(ctx, rootQuery, jobID).Scan(&rootURL)
		if rootURL == "" {
			rootURL = "unknown"
		}

		pagesQuery := `
			SELECT DISTINCT
				u.id,
				u.url,
				COALESCE(j.depth, 0) as depth,
				COALESCE(c.title, 'No Title') as title,
				c.metadata_str,
				c."htmlSource",
				COALESCE(m."httpStatusCode", 200) as http_status,
				COALESCE(m."contentType", 'text/html') as content_type,
				COALESCE(m."contentLength", 0) as content_length
			FROM job j
			JOIN url u ON j.url_id = u.id
			LEFT JOIN content c ON c.url_id = u.id
			LEFT JOIN metadata m ON m.url_id = u.id
			WHERE j.job_id = $1

			UNION

			SELECT DISTINCT
				u.id,
				u.url,
				COALESCE(ll.depth, 0) as depth,
				COALESCE(c.title, 'No Title') as title,
				c.metadata_str,
				c."htmlSource",
				COALESCE(m."httpStatusCode", 200) as http_status,
				COALESCE(m."contentType", 'text/html') as content_type,
				COALESCE(m."contentLength", 0) as content_length
			FROM link_log ll
			JOIN url u ON ll.url_id = u.id
			JOIN job j ON ll.job_id = j.id
			LEFT JOIN content c ON c.url_id = u.id
			LEFT JOIN metadata m ON m.url_id = u.id
			WHERE j.job_id = $1
			ORDER BY depth ASC, id ASC;
		`

		rows, err := e.Pool.Query(ctx, pagesQuery, jobID)
		if err != nil {
			log.Printf("warning: query export pages failed for job %s: %v", jobID, err)
		} else {
			defer rows.Close()
			pageIdx := 1
			for rows.Next() {
				var p pageData
				if err := rows.Scan(
					&p.urlID,
					&p.url,
					&p.depth,
					&p.title,
					&p.metadataStr,
					&p.htmlSource,
					&p.httpStatus,
					&p.contentType,
					&p.contentLength,
				); err != nil {
					log.Printf("error scanning export page row: %v", err)
					continue
				}

				filePath := fmt.Sprintf("pages/%06d.html", pageIdx)
				urlIDToFilePath[p.urlID] = filePath
				urlStrToFilePath[p.url] = filePath
				urlIDs = append(urlIDs, p.urlID)

				fetchedPages = append(fetchedPages, p)
				pageIdx++
			}
		}
	}

	outboundLinksMap := make(map[int][]ManifestLink)
	if e != nil && e.Pool != nil && len(urlIDs) > 0 {
		linksQuery := `
			SELECT
				l."sourceUrl_id",
				l."targetUrl",
				COALESCE(l."anchorText", '') as anchor_text,
				COALESCE(l."linkType", '') as link_type
			FROM links l
			WHERE l."sourceUrl_id" = ANY($1);
		`
		linkRows, err := e.Pool.Query(ctx, linksQuery, urlIDs)
		if err == nil {
			defer linkRows.Close()
			for linkRows.Next() {
				var srcID int
				var targetURL, anchorText, linkType string
				if err := linkRows.Scan(&srcID, &targetURL, &anchorText, &linkType); err == nil {
					targetFile := urlStrToFilePath[targetURL]
					outboundLinksMap[srcID] = append(outboundLinksMap[srcID], ManifestLink{
						TargetURL:  targetURL,
						TargetFile: targetFile,
						AnchorText: anchorText,
						LinkType:   linkType,
					})
				}
			}
		}
	}

	manifest := Manifest{
		Version:    "1.0",
		JobID:      jobID,
		ExportedAt: time.Now().UTC().Format(time.RFC3339),
		RootURL:    rootURL,
		TotalPages: len(fetchedPages),
		Pages:      make([]ManifestPage, 0, len(fetchedPages)),
	}

	zipBuf := new(bytes.Buffer)
	zipWriter := zip.NewWriter(zipBuf)

	for i, p := range fetchedPages {
		manifestPage := ManifestPage{
			ID:            i + 1,
			File:          urlIDToFilePath[p.urlID],
			URL:           p.url,
			Title:         p.title,
			Depth:         p.depth,
			HTTPStatus:    p.httpStatus,
			ContentType:   p.contentType,
			ContentLength: p.contentLength,
			MetadataStr:   p.metadataStr,
			OutboundLinks: outboundLinksMap[p.urlID],
		}
		if manifestPage.OutboundLinks == nil {
			manifestPage.OutboundLinks = make([]ManifestLink, 0)
		}
		manifest.Pages = append(manifest.Pages, manifestPage)

		w, err := zipWriter.Create(manifestPage.File)
		if err != nil {
			return nil, fmt.Errorf("failed to create zip entry %s: %w", manifestPage.File, err)
		}

		htmlContent := ""
		if p.htmlSource != nil && *p.htmlSource != "" {
			htmlContent = *p.htmlSource
		} else {
			htmlContent = fmt.Sprintf("<!DOCTYPE html><html><head><title>%s</title></head><body><h1>Page %s</h1><p>Status: %d</p></body></html>", p.title, p.url, p.httpStatus)
		}

		if _, err := w.Write([]byte(htmlContent)); err != nil {
			return nil, fmt.Errorf("failed to write zip file content: %w", err)
		}
	}

	manifestBytes, err := json.MarshalIndent(manifest, "", "  ")
	if err != nil {
		return nil, fmt.Errorf("failed to marshal manifest: %w", err)
	}

	mw, err := zipWriter.Create("manifest.json")
	if err != nil {
		return nil, fmt.Errorf("failed to create manifest.json in zip: %w", err)
	}
	if _, err := mw.Write(manifestBytes); err != nil {
		return nil, fmt.Errorf("failed to write manifest.json: %w", err)
	}

	if err := zipWriter.Close(); err != nil {
		return nil, fmt.Errorf("failed to finalize zip archive: %w", err)
	}

	return zipBuf.Bytes(), nil
}

func StreamZipOverWebSocket(jobID string, zipBytes []byte, sendFunc func(msg map[string]any)) {
	totalBytes := len(zipBytes)
	totalChunks := (totalBytes + ChunkSize - 1) / ChunkSize
	if totalChunks == 0 {
		totalChunks = 1
	}

	filename := fmt.Sprintf("crawl-job-%s.zip", jobID)

	sendFunc(map[string]any{
		"kind": "EXPORT_START",
		"data": map[string]any{
			"job_id":       jobID,
			"total_bytes":  totalBytes,
			"total_chunks": totalChunks,
			"filename":     filename,
		},
	})

	for i := 0; i < totalChunks; i++ {
		start := i * ChunkSize
		end := start + ChunkSize
		if end > totalBytes {
			end = totalBytes
		}

		chunkData := zipBytes[start:end]
		base64Payload := base64.StdEncoding.EncodeToString(chunkData)

		sendFunc(map[string]any{
			"kind": "EXPORT_CHUNK",
			"data": map[string]any{
				"job_id":      jobID,
				"chunk_index": i,
				"payload":     base64Payload,
			},
		})
		time.Sleep(2 * time.Millisecond)
	}

	sendFunc(map[string]any{
		"kind": "EXPORT_END",
		"data": map[string]any{
			"job_id": jobID,
		},
	})
	log.Printf("successfully streamed export archive for job %s (%d bytes, %d chunks)", jobID, totalBytes, totalChunks)
}
