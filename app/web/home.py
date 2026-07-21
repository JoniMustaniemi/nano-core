from html import escape
from textwrap import dedent

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.config import get_settings
from app.web.tool_commands import list_tool_commands

router = APIRouter(tags=["web"])


@router.get("/api/tool-commands")
def tool_commands() -> list[dict[str, str]]:
    """
    Return quick-command buttons for the web UI.

    Returns:
        Tool command definitions.
    """
    return list_tool_commands()


@router.get("/", response_class=HTMLResponse)
def home() -> str:
    """
    Render the home page.

    Returns:
        Generated or formatted string value.
    """
    settings = get_settings()
    app_name = escape(settings.app_name)
    return dedent(
        f"""
        <!doctype html>
        <html lang="en">
          <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <title>{app_name}</title>
            <link rel="stylesheet" href="/static/home.css?v=tool-drawer-2" />
            <script defer src="/static/home.js?v=tool-drawer-4"></script>
          </head>
          <body>
            <button
              id="commands-toggle"
              class="ghost commands-toggle"
              type="button"
              aria-expanded="false"
              aria-controls="commands-panel"
            >
              Commands
            </button>
            <main class="shell">
              <section class="masthead">
                <h1 class="title"><span>Nano</span></h1>
                <section class="state-strip" aria-label="Nano state">
                  <div class="state-segment active" data-state-segment="standby">
                    <span class="state-led" aria-hidden="true"></span>
                    <span class="state-label">Standby</span>
                  </div>
                  <div class="state-segment" data-state-segment="working">
                    <span class="state-led" aria-hidden="true"></span>
                    <span class="state-label">Working</span>
                  </div>
                  <div class="state-segment" data-state-segment="listening">
                    <span class="state-led" aria-hidden="true"></span>
                    <span class="state-label">Listening</span>
                  </div>
                </section>
                <div class="sr-only" id="state-line">standby</div>
              </section>

              <section class="core">
                <div class="input-shell">
                  <div class="prompt">Transmit to Nano</div>
                  <label class="sr-only" for="message">Message for Nano</label>
                  <textarea id="message" placeholder="Type to Nano..."></textarea>
                  <div class="actions">
                    <button id="send" type="button">Send</button>
                    <button id="voice-listen" class="ghost" type="button">Start Listening</button>
                  </div>
                  <div class="reply-status" id="voice-status">Voice standby.</div>
                  <div class="reply-status" id="reply-status"></div>
                </div>

                <section class="answer">
                  <button
                    id="copy-answer"
                    class="answer-copy"
                    type="button"
                    aria-label="Copy answer"
                    title="Copy answer"
                  >
                    <svg
                      aria-hidden="true"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                    >
                      <rect x="8" y="8" width="12" height="12" rx="2"></rect>
                      <path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"></path>
                    </svg>
                  </button>
                  <pre id="answer-output" class="answer-output empty">Awaiting signal.</pre>
                  <audio id="voice-audio" hidden preload="none"></audio>
                </section>

                <details class="brains">
                  <summary>
                    <span>Nano's brains</span>
                    <span class="brains-meta" id="brains-status">sealed</span>
                  </summary>
                  <div class="brains-body">
                    <textarea
                      id="activity-log"
                      class="terminal"
                      readonly
                      spellcheck="false"
                      placeholder="No internal activity yet."
                    ></textarea>
                  </div>
                </details>

                <details class="storage">
                  <summary>
                    <span>Stored data</span>
                    <span class="brains-meta" id="storage-status">sealed</span>
                  </summary>
                  <div class="storage-body">
                    <textarea
                      id="storage-log"
                      class="terminal"
                      readonly
                      spellcheck="false"
                      placeholder="No storage snapshot loaded yet."
                    ></textarea>
                  </div>
                </details>
              </section>
            </main>

            <div id="commands-drawer" class="commands-drawer" aria-hidden="true">
              <button
                id="commands-backdrop"
                class="commands-backdrop"
                type="button"
                aria-label="Close commands drawer"
                tabindex="-1"
              ></button>
              <aside
                id="commands-panel"
                class="commands-panel"
                role="dialog"
                aria-modal="true"
                aria-labelledby="commands-title"
              >
                <header class="commands-header">
                  <div>
                    <h2 id="commands-title">Commands</h2>
                    <p class="commands-subtitle">Run a tool without typing.</p>
                  </div>
                  <button id="commands-close" class="ghost commands-close" type="button" aria-label="Close commands">
                    Close
                  </button>
                </header>
                <div id="commands-list" class="commands-list"></div>
              </aside>
            </div>
          </body>
        </html>
        """
    ).strip()
