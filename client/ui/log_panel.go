package ui

import (
	"fmt"
	"strings"
	"time"

	"charm.land/lipgloss/v2"
)

// LogEventMsg is the tea.Msg sent when a new server event arrives.
type LogEventMsg struct {
	Payload string
}

// logEntry is a single timestamped log line.
type logEntry struct {
	time    time.Time
	payload string
}

// LogPanel holds state for the scrollable log viewer.
type LogPanel struct {
	entries    []logEntry
	maxLines   int // how many entries to keep in memory
	viewHeight int // visible rows inside the box
	viewWidth  int // visible cols inside the box
	scrollOff  int // 0 = pinned to bottom (auto-scroll)
}

// NewLogPanel creates a log panel with sensible defaults.
func NewLogPanel() LogPanel {
	return LogPanel{
		entries:    make([]logEntry, 0, 256),
		maxLines:   500,
		viewHeight: 14,
		viewWidth:  78,
		scrollOff:  0,
	}
}

// Push adds a new log entry.
func (lp *LogPanel) Push(payload string) {
	lp.entries = append(lp.entries, logEntry{
		time:    time.Now(),
		payload: payload,
	})
	// Evict old entries if we exceed the cap.
	if len(lp.entries) > lp.maxLines {
		lp.entries = lp.entries[len(lp.entries)-lp.maxLines:]
	}
	// Keep pinned to bottom when new data arrives (auto-scroll).
	lp.scrollOff = 0
}

// ScrollUp moves the viewport up.
func (lp *LogPanel) ScrollUp(n int) {
	maxOff := len(lp.entries) - lp.viewHeight
	if maxOff < 0 {
		maxOff = 0
	}
	lp.scrollOff += n
	if lp.scrollOff > maxOff {
		lp.scrollOff = maxOff
	}
}

// ScrollDown moves the viewport down (towards latest).
func (lp *LogPanel) ScrollDown(n int) {
	lp.scrollOff -= n
	if lp.scrollOff < 0 {
		lp.scrollOff = 0
	}
}

// SetSize adjusts the panel to fit the terminal.
func (lp *LogPanel) SetSize(width, height int) {
	// Reserve 2 for the border on each side, 2 for title line + padding.
	lp.viewWidth = width - 4
	if lp.viewWidth < 20 {
		lp.viewWidth = 20
	}
	lp.viewHeight = height
	if lp.viewHeight < 3 {
		lp.viewHeight = 3
	}
}

// View renders the log panel as a styled string.
func (lp *LogPanel) View() string {
	// ── styles ──────────────────────────────────────────────
	borderColor := lipgloss.Color("63")  // soft purple
	tsColor := lipgloss.Color("243")     // dim grey
	textColor := lipgloss.Color("252")   // light grey
	headerColor := lipgloss.Color("212") // pink
	emptyColor := lipgloss.Color("240")  // muted

	boxStyle := lipgloss.NewStyle().
		Border(lipgloss.RoundedBorder()).
		BorderForeground(borderColor).
		Padding(0, 1).
		Width(lp.viewWidth + 2) // +2 for left/right padding

	titleStyle := lipgloss.NewStyle().
		Foreground(headerColor).
		Bold(true)

	tsStyle := lipgloss.NewStyle().Foreground(tsColor)
	msgStyle := lipgloss.NewStyle().Foreground(textColor)
	dimStyle := lipgloss.NewStyle().Foreground(emptyColor).Italic(true)

	// ── build visible lines ─────────────────────────────────
	var lines []string

	if len(lp.entries) == 0 {
		// Show a friendly empty state.
		pad := lp.viewHeight / 2
		for range pad {
			lines = append(lines, "")
		}
		lines = append(lines, dimStyle.Render("  ⏳ waiting for server events..."))
		for len(lines) < lp.viewHeight {
			lines = append(lines, "")
		}
	} else {
		// Determine the window of entries to show.
		end := len(lp.entries) - lp.scrollOff
		start := end - lp.viewHeight
		if start < 0 {
			start = 0
		}
		if end < 0 {
			end = 0
		}

		for _, e := range lp.entries[start:end] {
			ts := tsStyle.Render(e.time.Format("15:04:05"))
			msg := msgStyle.Render(truncate(e.payload, lp.viewWidth-12))
			lines = append(lines, fmt.Sprintf(" %s │ %s", ts, msg))
		}

		// Pad remaining rows if fewer entries than viewHeight.
		for len(lines) < lp.viewHeight {
			lines = append(lines, "")
		}
	}

	content := strings.Join(lines, "\n")

	// ── header ──────────────────────────────────────────────
	countStr := dimStyle.Render(fmt.Sprintf(" (%d)", len(lp.entries)))
	scrollHint := ""
	if lp.scrollOff > 0 {
		scrollHint = dimStyle.Render(fmt.Sprintf("  ↑ %d more below", lp.scrollOff))
	}
	header := titleStyle.Render("  ◉ Server Events") + countStr + scrollHint

	return header + "\n" + boxStyle.Render(content)
}

// truncate cuts a string to maxLen, adding an ellipsis if truncated.
func truncate(s string, maxLen int) string {
	if maxLen <= 0 {
		return ""
	}
	// Work on runes to avoid cutting multi-byte chars.
	runes := []rune(s)
	if len(runes) <= maxLen {
		return s
	}
	if maxLen <= 3 {
		return string(runes[:maxLen])
	}
	return string(runes[:maxLen-1]) + "…"
}
