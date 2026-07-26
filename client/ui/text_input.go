package ui

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"

	"charm.land/bubbles/v2/cursor"
	"charm.land/bubbles/v2/textinput"
	tea "charm.land/bubbletea/v2"
	"charm.land/lipgloss/v2"

	ws "github.com/steel77-7/Web-Swab/socket"
)

var (
	focusedStyle        = lipgloss.NewStyle().Foreground(lipgloss.Color("205"))
	blurredStyle        = lipgloss.NewStyle().Foreground(lipgloss.Color("240"))
	cursorStyle         = focusedStyle
	noStyle             = lipgloss.NewStyle()
	helpStyle           = blurredStyle
	cursorModeHelpStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("244"))

	focusedButton = focusedStyle.Render("[ Submit ]")
	blurredButton = fmt.Sprintf("[ %s ]", blurredStyle.Render("Submit"))
)

type model struct {
	focusIndex int
	inputs     []textinput.Model
	cursorMode cursor.Mode
	quitting   bool

	logPanel LogPanel
	width    int
	height   int

	exportChunks map[string]map[int][]byte
	exportTotals map[string]int
}

func waitForServerEvent() tea.Msg {
	data := <-ws.LogChan
	return LogEventMsg{Payload: string(data)}
}

func initialModel() model {
	m := model{
		inputs:       make([]textinput.Model, 2),
		logPanel:     NewLogPanel(),
		exportChunks: make(map[string]map[int][]byte),
		exportTotals: make(map[string]int),
	}

	var t textinput.Model
	for i := range m.inputs {
		t = textinput.New()
		t.CharLimit = 64

		s := t.Styles()
		s.Cursor.Color = lipgloss.Color("205")
		s.Focused.Prompt = focusedStyle
		s.Focused.Text = focusedStyle
		s.Blurred.Prompt = blurredStyle
		s.Blurred.Text = blurredStyle
		t.SetStyles(s)

		switch i {
		case 0:
			t.Placeholder = "Url"
			t.Focus()
		case 1:
			t.Placeholder = "Depth"
			t.CharLimit = 3
			t.Validate = func(s string) error {
				_, err := strconv.Atoi(s)
				if err != nil {
					return fmt.Errorf("depth must be an integer")
				}
				return nil
			}
		}

		m.inputs[i] = t
	}

	return m
}

func (m model) Init() tea.Cmd {
	return tea.Batch(
		textinput.Blink,
		waitForServerEvent,
	)
}

func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {

	case LogEventMsg:
		displayStr := msg.Payload
		var envelope struct {
			Kind string          `json:"kind"`
			Data json.RawMessage `json:"data"`
		}
		if err := json.Unmarshal([]byte(msg.Payload), &envelope); err == nil && len(envelope.Data) > 0 {
			switch envelope.Kind {
			case "EXPORT_START":
				var startData struct {
					JobID       string `json:"job_id"`
					TotalBytes  int    `json:"total_bytes"`
					TotalChunks int    `json:"total_chunks"`
					Filename    string `json:"filename"`
				}
				if err := json.Unmarshal(envelope.Data, &startData); err == nil {
					if m.exportChunks == nil {
						m.exportChunks = make(map[string]map[int][]byte)
						m.exportTotals = make(map[string]int)
					}
					m.exportChunks[startData.JobID] = make(map[int][]byte)
					m.exportTotals[startData.JobID] = startData.TotalChunks
					displayStr = fmt.Sprintf("[EXPORT] Receiving %s (%d KB, %d chunks)...", startData.Filename, startData.TotalBytes/1024, startData.TotalChunks)
				}

			case "EXPORT_CHUNK":
				var chunkData struct {
					JobID      string `json:"job_id"`
					ChunkIndex int    `json:"chunk_index"`
					Payload    string `json:"payload"`
				}
				if err := json.Unmarshal(envelope.Data, &chunkData); err == nil {
					if rawBytes, err := base64.StdEncoding.DecodeString(chunkData.Payload); err == nil {
						if m.exportChunks == nil {
							m.exportChunks = make(map[string]map[int][]byte)
							m.exportTotals = make(map[string]int)
						}
						if _, ok := m.exportChunks[chunkData.JobID]; !ok {
							m.exportChunks[chunkData.JobID] = make(map[int][]byte)
						}
						m.exportChunks[chunkData.JobID][chunkData.ChunkIndex] = rawBytes
						tot := m.exportTotals[chunkData.JobID]
						rec := len(m.exportChunks[chunkData.JobID])
						pct := 0
						if tot > 0 {
							pct = (rec * 100) / tot
						}
						displayStr = fmt.Sprintf("[EXPORT] Downloading %s... %d%% (%d/%d chunks)", chunkData.JobID, pct, rec, tot)
					}
				}

			case "EXPORT_END":
				var endData struct {
					JobID string `json:"job_id"`
				}
				if err := json.Unmarshal(envelope.Data, &endData); err == nil {
					chunksMap := m.exportChunks[endData.JobID]
					tot := m.exportTotals[endData.JobID]
					if len(chunksMap) > 0 {
						var zipBuf bytes.Buffer
						for i := 0; i < tot; i++ {
							if chunk, ok := chunksMap[i]; ok {
								zipBuf.Write(chunk)
							}
						}
						filename := fmt.Sprintf("crawl-job-%s.zip", endData.JobID)
						if err := os.WriteFile(filename, zipBuf.Bytes(), 0644); err == nil {
							displayStr = fmt.Sprintf("[SUCCESS] Export download complete! Saved archive to ./%s", filename)
						} else {
							displayStr = fmt.Sprintf("[EXPORT ERROR] Failed to write %s: %v", filename, err)
						}
						delete(m.exportChunks, endData.JobID)
						delete(m.exportTotals, endData.JobID)
					} else {
						displayStr = fmt.Sprintf("[EXPORT ERROR] No chunks received for job %s", endData.JobID)
					}
				}

			case "LOG":
				var logData struct {
					JobID   string `json:"job_id"`
					Level   string `json:"level"`
					Message string `json:"message"`
				}
				var rawStr string
				if err := json.Unmarshal(envelope.Data, &rawStr); err == nil {
					if err := json.Unmarshal([]byte(rawStr), &logData); err == nil && logData.Message != "" {
						displayStr = fmt.Sprintf("[%s] %s", strings.ToUpper(logData.Level), logData.Message)
					} else {
						displayStr = rawStr
					}
				} else if err := json.Unmarshal(envelope.Data, &logData); err == nil && logData.Message != "" {
					displayStr = fmt.Sprintf("[%s] %s", strings.ToUpper(logData.Level), logData.Message)
				}
			}
		}
		m.logPanel.Push(displayStr)
		return m, waitForServerEvent

	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		logHeight := m.height*4/10 - 4
		if logHeight < 5 {
			logHeight = 5
		}
		m.logPanel.SetSize(m.width, logHeight)
		return m, nil

	case tea.KeyPressMsg:
		switch msg.String() {
		case "ctrl+c", "esc":
			m.quitting = true
			return m, tea.Quit

		case "ctrl+k":
			m.logPanel.ScrollUp(3)
			return m, nil
		case "ctrl+j":
			m.logPanel.ScrollDown(3)
			return m, nil

		case "ctrl+r":
			m.cursorMode++
			if m.cursorMode > cursor.CursorHide {
				m.cursorMode = cursor.CursorBlink
			}
			cmds := make([]tea.Cmd, len(m.inputs))
			for i := range m.inputs {
				s := m.inputs[i].Styles()
				s.Cursor.Blink = m.cursorMode == cursor.CursorBlink
				m.inputs[i].SetStyles(s)
			}
			return m, tea.Batch(cmds...)

		case "tab", "shift+tab", "enter", "up", "down":
			s := msg.String()

			if s == "enter" && m.focusIndex == len(m.inputs) {
				targetURL := strings.TrimSpace(m.inputs[0].Value())
				if targetURL == "" {
					m.logPanel.Push("[CLIENT ERROR] URL cannot be empty")
					return m, nil
				}

				depth := 1
				if d, err := strconv.Atoi(m.inputs[1].Value()); err == nil && d > 0 {
					depth = d
				}

				jobID := fmt.Sprintf("job-%d", time.Now().UnixNano()/1e6)
				jobData := map[string]any{
					"id":     jobID,
					"status": "pending",
					"url":    targetURL,
					"depth":  depth,
				}

				jobBytes, err := json.Marshal(jobData)
				if err != nil {
					m.logPanel.Push(fmt.Sprintf("[CLIENT ERROR] Failed to serialize job: %v", err))
					return m, nil
				}

				go func() {
					ws.SendChan <- jobBytes
				}()

				m.logPanel.Push(fmt.Sprintf("[CLIENT] Submitted job %s for %s (depth %d)", jobID, targetURL, depth))
				m.inputs[0].SetValue("")
				m.inputs[1].SetValue("")
				m.focusIndex = 0
				m.inputs[0].Focus()
				m.inputs[1].Blur()
				return m, nil
			}

			if s == "up" || s == "shift+tab" {
				m.focusIndex--
			} else {
				m.focusIndex++
			}

			if m.focusIndex > len(m.inputs) {
				m.focusIndex = 0
			} else if m.focusIndex < 0 {
				m.focusIndex = len(m.inputs)
			}

			cmds := make([]tea.Cmd, len(m.inputs))
			for i := 0; i <= len(m.inputs)-1; i++ {
				if i == m.focusIndex {
					cmds[i] = m.inputs[i].Focus()
					continue
				}
				m.inputs[i].Blur()
			}

			return m, tea.Batch(cmds...)
		}
	}

	cmd := m.updateInputs(msg)

	return m, cmd
}

func (m *model) updateInputs(msg tea.Msg) tea.Cmd {
	cmds := make([]tea.Cmd, len(m.inputs))

	for i := range m.inputs {
		m.inputs[i], cmds[i] = m.inputs[i].Update(msg)
	}

	return tea.Batch(cmds...)
}

func (m model) View() tea.View {
	var b strings.Builder
	var c *tea.Cursor

	titleStyle := lipgloss.NewStyle().
		Foreground(lipgloss.Color("205")).
		Bold(true)
	b.WriteString(titleStyle.Render("🕷  Web-Swab"))
	b.WriteString("\n\n")

	for i, in := range m.inputs {
		b.WriteString(m.inputs[i].View())
		if i < len(m.inputs)-1 {
			b.WriteRune('\n')
		}
		if m.cursorMode != cursor.CursorHide && in.Focused() {
			c = in.Cursor()
			if c != nil {
				c.Y += i + 2
			}
		}
	}

	button := &blurredButton
	if m.focusIndex == len(m.inputs) {
		button = &focusedButton
	}
	fmt.Fprintf(&b, "\n\n%s\n\n", *button)

	b.WriteString(m.logPanel.View())
	b.WriteRune('\n')

	b.WriteString(helpStyle.Render("ctrl+j/k scroll logs • esc quit"))

	if m.quitting {
		b.WriteRune('\n')
	}

	v := tea.NewView(b.String())
	v.Cursor = c
	return v
}

func Run() {
	if _, err := tea.NewProgram(initialModel()).Run(); err != nil {
		fmt.Printf("could not start program: %s\n", err)
		os.Exit(1)
	}
}
