from html import escape
from textwrap import dedent

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.config import get_settings

router = APIRouter(tags=["web"])


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
            <link rel="stylesheet" href="/static/home.css" />
            <script defer src="/static/home.js"></script>
          </head>
          <body>
            <main class="shell">
              <section class="masthead">
                <h1 class="title"><span>Nano</span></h1>
                <div class="status-line" id="state-line">standby</div>
              </section>

              <section class="core">
                <div class="input-shell">
                  <div class="prompt">Transmit to Nano</div>
                  <label class="sr-only" for="message">Message for Nano</label>
                  <textarea id="message" placeholder="Type to Nano..."></textarea>
                  <div class="actions">
                    <button id="send" type="button">Send</button>
                    <button id="voice-listen" class="ghost" type="button">Start Listening</button>
                    <button id="stop-audio" class="ghost" type="button">Stop Audio</button>
                    <button id="copy-answer" class="ghost" type="button">Copy Answer</button>
                  </div>
                  <div class="reply-status" id="voice-status">Voice standby.</div>
                  <div class="reply-status" id="reply-status"></div>
                </div>

                <section class="answer">
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
          </body>
        </html>
        """
    ).strip()
