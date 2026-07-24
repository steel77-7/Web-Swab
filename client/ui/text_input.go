package ui

import (
	"fmt"
	"os"
	"strconv"
	"strings"

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
}

// waitForServerEvent listens on the socket's LogChan and returns a
// LogEventMsg when something arrives. Bubble Tea re-invokes this as
// a Cmd after each message, creating a continuous listener loop.
func waitForServerEvent() tea.Msg {
	data := <-ws.LogChan
	return LogEventMsg{Payload: string(data)}
}

func initialModel() model {
	m := model{
		inputs:   make([]textinput.Model, 2),
		logPanel: NewLogPanel(),
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

	// ── server log event ────────────────────────────────────
	case LogEventMsg:
		m.logPanel.Push(msg.Payload)
		// Re-subscribe to wait for the next event.
		return m, waitForServerEvent

	// ── terminal resize ─────────────────────────────────────
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		// Give roughly bottom 40% of the terminal to the log panel.
		logHeight := m.height*4/10 - 4
		if logHeight < 5 {
			logHeight = 5
		}
		m.logPanel.SetSize(m.width, logHeight)
		return m, nil

	// ── keyboard ────────────────────────────────────────────
	case tea.KeyPressMsg:
		switch msg.String() {
		case "ctrl+c", "esc":
			m.quitting = true
			return m, tea.Quit

		// Scroll log panel
		case "ctrl+k":
			m.logPanel.ScrollUp(3)
			return m, nil
		case "ctrl+j":
			m.logPanel.ScrollDown(3)
			return m, nil

		// Change cursor mode
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

		// Navigate inputs
		case "tab", "shift+tab", "enter", "up", "down":
			s := msg.String()

			// Submit
			if s == "enter" && m.focusIndex == len(m.inputs) {
				return m, tea.Quit
			}

			// Cycle indexes
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

	// Handle character input and blinking
	cmd := m.updateInputs(msg)

	return m, cmd
}

func (m *model) updateInputs(msg tea.Msg) tea.Cmd {
	cmds := make([]tea.Cmd, len(m.inputs))

	// Only text inputs with Focus() set will respond, so it's safe to simply
	// update all of them here without any further logic.
	for i := range m.inputs {
		m.inputs[i], cmds[i] = m.inputs[i].Update(msg)
	}

	return tea.Batch(cmds...)
}

func (m model) View() tea.View {
	var b strings.Builder
	var c *tea.Cursor

	// ── title ───────────────────────────────────────────────
	titleStyle := lipgloss.NewStyle().
		Foreground(lipgloss.Color("205")).
		Bold(true)
	b.WriteString(titleStyle.Render("🕷  Web-Swab"))
	b.WriteString("\n\n")

	// ── input form ──────────────────────────────────────────
	for i, in := range m.inputs {
		b.WriteString(m.inputs[i].View())
		if i < len(m.inputs)-1 {
			b.WriteRune('\n')
		}
		if m.cursorMode != cursor.CursorHide && in.Focused() {
			c = in.Cursor()
			if c != nil {
				// Offset cursor Y for title lines above + input index.
				c.Y += i + 2 // 2 = title + blank line
			}
		}
	}

	button := &blurredButton
	if m.focusIndex == len(m.inputs) {
		button = &focusedButton
	}
	fmt.Fprintf(&b, "\n\n%s\n\n", *button)

	// ── log panel ───────────────────────────────────────────
	b.WriteString(m.logPanel.View())
	b.WriteRune('\n')

	// ── help ────────────────────────────────────────────────
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
