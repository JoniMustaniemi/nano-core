from html import escape
from textwrap import dedent

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.config import get_settings

router = APIRouter(tags=["web"])


@router.get("/", response_class=HTMLResponse)
def home() -> str:
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
            <style>
              :root {{
                color-scheme: dark;
                --bg-top: #050b12;
                --bg-bottom: #09131d;
                --panel: rgba(7, 14, 22, 0.84);
                --panel-border: rgba(118, 211, 155, 0.16);
                --panel-strong: rgba(118, 211, 155, 0.26);
                --text: #ecfff3;
                --muted: #8ea99a;
                --accent: #76d39b;
                --accent-strong: #b5ffd0;
                --warning: #f4c15d;
                --error: #ff8a7a;
                --shadow: 0 24px 80px rgba(0, 0, 0, 0.44);
              }}
              * {{
                box-sizing: border-box;
              }}
              body {{
                margin: 0;
                min-height: 100vh;
                font-family: "Segoe UI", system-ui, sans-serif;
                color: var(--text);
                background:
                  radial-gradient(circle at 50% 0%, rgba(118, 211, 155, 0.16), transparent 22%),
                  radial-gradient(circle at 10% 10%, rgba(118, 211, 155, 0.08), transparent 24%),
                  linear-gradient(180deg, var(--bg-top) 0%, var(--bg-bottom) 100%);
              }}
              .shell {{
                width: min(880px, calc(100vw - 32px));
                margin: 0 auto;
                padding: 54px 0 64px;
              }}
              .masthead {{
                text-align: center;
                margin-bottom: 28px;
              }}
              .title {{
                margin: 0;
                font-size: clamp(3.2rem, 11vw, 7rem);
                line-height: 0.9;
                letter-spacing: -0.08em;
                font-weight: 800;
              }}
              .title span {{
                display: inline-block;
                color: var(--accent-strong);
                text-shadow: 0 0 30px rgba(118, 211, 155, 0.18);
              }}
              .status-line {{
                margin-top: 12px;
                color: var(--muted);
                font-size: 0.92rem;
                letter-spacing: 0.14em;
                text-transform: uppercase;
              }}
              .core {{
                border: 1px solid var(--panel-border);
                border-radius: 30px;
                padding: 22px;
                background:
                  linear-gradient(180deg, rgba(8, 15, 24, 0.94), rgba(7, 13, 20, 0.86)),
                  radial-gradient(circle at top right, rgba(118, 211, 155, 0.08), transparent 30%);
                box-shadow: var(--shadow);
                backdrop-filter: blur(18px);
              }}
              .input-shell {{
                display: grid;
                gap: 14px;
              }}
              .prompt {{
                display: flex;
                align-items: center;
                gap: 12px;
                color: var(--accent-strong);
                font: 700 0.92rem/1 "Cascadia Mono", "Consolas", monospace;
                letter-spacing: 0.08em;
                text-transform: uppercase;
              }}
              .prompt::before {{
                content: ">";
                color: var(--accent);
              }}
              textarea {{
                width: 100%;
                min-height: 132px;
                resize: vertical;
                border: 1px solid rgba(118, 211, 155, 0.18);
                border-radius: 22px;
                padding: 18px 20px;
                background:
                  linear-gradient(180deg, rgba(3, 8, 14, 0.98), rgba(5, 10, 17, 0.92));
                color: var(--text);
                font: 500 1rem/1.6 "Segoe UI", system-ui, sans-serif;
                outline: none;
                transition: border-color 140ms ease, box-shadow 140ms ease;
              }}
              textarea:focus {{
                border-color: rgba(118, 211, 155, 0.46);
                box-shadow: 0 0 0 4px rgba(118, 211, 155, 0.1);
              }}
              .actions {{
                display: flex;
                flex-wrap: wrap;
                gap: 12px;
                align-items: center;
              }}
              button {{
                border: 0;
                border-radius: 999px;
                padding: 12px 18px;
                background: linear-gradient(135deg, var(--accent), var(--accent-strong));
                color: #04110a;
                font-weight: 800;
                cursor: pointer;
                transition: transform 140ms ease, filter 140ms ease, opacity 140ms ease;
              }}
              button:hover {{
                transform: translateY(-1px);
                filter: brightness(1.03);
              }}
              button:disabled {{
                opacity: 0.55;
                cursor: wait;
              }}
              .ghost {{
                border: 1px solid rgba(255, 255, 255, 0.08);
                background: rgba(255, 255, 255, 0.03);
                color: var(--text);
              }}
              .reply-status {{
                color: var(--muted);
                font-size: 0.92rem;
                min-height: 1.4em;
              }}
              .answer {{
                margin-top: 18px;
                padding: 18px;
                border-radius: 24px;
                border: 1px solid var(--panel-strong);
                background:
                  linear-gradient(180deg, rgba(3, 8, 14, 0.96), rgba(4, 9, 14, 0.9)),
                  radial-gradient(circle at top left, rgba(118, 211, 155, 0.07), transparent 36%);
              }}
              .answer-output {{
                margin: 0;
                min-height: 92px;
                color: var(--text);
                white-space: pre-wrap;
                font-size: 1.02rem;
                line-height: 1.75;
              }}
              .answer-output.empty {{
                color: var(--muted);
              }}
              details.brains {{
                margin-top: 18px;
                border: 1px solid rgba(118, 211, 155, 0.14);
                border-radius: 24px;
                background: rgba(6, 12, 19, 0.72);
                overflow: hidden;
              }}
              details.brains > summary {{
                list-style: none;
                cursor: pointer;
                padding: 16px 18px;
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 12px;
                color: var(--accent-strong);
                font: 700 0.92rem/1 "Cascadia Mono", "Consolas", monospace;
                letter-spacing: 0.08em;
                text-transform: uppercase;
              }}
              details.brains > summary::-webkit-details-marker {{
                display: none;
              }}
              .brains-meta {{
                color: var(--muted);
                font-size: 0.78rem;
                letter-spacing: 0.08em;
              }}
              .brains-body {{
                padding: 0 18px 18px;
              }}
              .terminal {{
                width: 100%;
                min-height: 260px;
                resize: vertical;
                border: 1px solid rgba(118, 211, 155, 0.12);
                border-radius: 18px;
                padding: 16px;
                background: rgba(2, 6, 10, 0.96);
                color: #dfffe7;
                font: 600 0.91rem/1.55 "Cascadia Mono", "Consolas", monospace;
                outline: none;
                white-space: pre;
                overflow: auto;
              }}
              .terminal::placeholder {{
                color: rgba(142, 169, 154, 0.72);
              }}
              .sr-only {{
                position: absolute;
                width: 1px;
                height: 1px;
                padding: 0;
                margin: -1px;
                overflow: hidden;
                clip: rect(0, 0, 0, 0);
                white-space: nowrap;
                border: 0;
              }}
            </style>
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
                  <textarea
                    id="message"
                    placeholder="Type to Nano..."
                  ></textarea>
                  <div class="actions">
                    <button id="send" type="button">Send</button>
                    <button id="stop-audio" class="ghost" type="button">Stop Audio</button>
                    <button id="copy-answer" class="ghost" type="button">Copy Answer</button>
                  </div>
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
              </section>
            </main>

            <script>
              const stateLine = document.getElementById("state-line");
              const activityLog = document.getElementById("activity-log");
              const replyStatus = document.getElementById("reply-status");
              const messageBox = document.getElementById("message");
              const sendButton = document.getElementById("send");
              const stopAudioButton = document.getElementById("stop-audio");
              const copyAnswerButton = document.getElementById("copy-answer");
              const answerOutput = document.getElementById("answer-output");
              const voiceAudio = document.getElementById("voice-audio");
              const brainsPanel = document.querySelector(".brains");
              const brainsStatus = document.getElementById("brains-status");
              let currentVoiceUrl = null;
              let voiceAvailable = false;

              function applyState(snapshot) {{
                stateLine.textContent = snapshot.state || "standby";
              }}

              function formatEvent(event) {{
                const stamp = event.created_at
                  ? new Date(event.created_at).toLocaleTimeString()
                  : "--:--:--";
                const source = event.source || "system";
                const title = event.title || "Activity";
                const detailText = event.detail || event.state || "";
                const detailSuffix = detailText ? `\\n    ${{detailText}}` : "";
                return `[${{stamp}}] ${{source}} | ${{title}}${{detailSuffix}}`;
              }}

              function refreshEvents(snapshot) {{
                const events = Array.isArray(snapshot.events)
                  ? snapshot.events.slice().reverse()
                  : [];
                activityLog.value = events.map((event) => formatEvent(event)).join("\\n\\n");
                activityLog.scrollTop = activityLog.scrollHeight;
              }}

              function appendEvent(event) {{
                const line = formatEvent(event);
                activityLog.value = activityLog.value
                  ? `${{activityLog.value}}\\n\\n${{line}}`
                  : line;
                activityLog.scrollTop = activityLog.scrollHeight;
              }}

              function setAnswer(text) {{
                const content = text.trim();
                if (!content) {{
                  answerOutput.textContent = "Awaiting signal.";
                  answerOutput.classList.add("empty");
                  return;
                }}
                answerOutput.textContent = content;
                answerOutput.classList.remove("empty");
              }}

              function stopVoicePlayback() {{
                voiceAudio.pause();
                voiceAudio.currentTime = 0;
                if (currentVoiceUrl) {{
                  URL.revokeObjectURL(currentVoiceUrl);
                  currentVoiceUrl = null;
                }}
                voiceAudio.removeAttribute("src");
              }}

              async function playVoice(text) {{
                if (!voiceAvailable || !text.trim()) {{
                  return;
                }}
                stopVoicePlayback();
                try {{
                  const response = await fetch("/api/voice", {{
                    method: "POST",
                    headers: {{
                      "Content-Type": "application/json",
                    }},
                    body: JSON.stringify({{ text }}),
                  }});
                  if (!response.ok) {{
                    const data = await response.json().catch(() => null);
                    throw new Error(data?.detail || "Voice playback failed.");
                  }}
                  const blob = await response.blob();
                  currentVoiceUrl = URL.createObjectURL(blob);
                  voiceAudio.src = currentVoiceUrl;
                  await voiceAudio.play();
                }} catch (error) {{
                  replyStatus.textContent =
                    `Nano answered, but voice playback failed: ${{error.message}}`;
                }}
              }}

              async function loadSnapshot() {{
                const response = await fetch("/api/status");
                if (!response.ok) {{
                  throw new Error("Could not load Nano status.");
                }}
                return response.json();
              }}

              async function bootstrap() {{
                try {{
                  const snapshot = await loadSnapshot();
                  applyState(snapshot);
                  refreshEvents(snapshot);
                  const voiceResponse = await fetch("/api/voice/status");
                  if (voiceResponse.ok) {{
                    const voice = await voiceResponse.json();
                    voiceAvailable = Boolean(voice.available);
                    stopAudioButton.disabled = !voiceAvailable;
                    if (!voiceAvailable && typeof voice.detail === "string") {{
                      replyStatus.textContent = voice.detail;
                    }}
                  }}
                }} catch (error) {{
                  replyStatus.textContent = error.message;
                }}
              }}

              function listen() {{
                const source = new EventSource("/events");
                source.addEventListener("activity", (event) => {{
                  const payload = JSON.parse(event.data);
                  applyState({{ state: payload.state }});
                  appendEvent(payload);
                }});
                source.onerror = () => {{
                  stateLine.textContent = "reconnecting";
                }};
              }}

              async function sendMessage() {{
                const message = messageBox.value.trim();
                if (!message) {{
                  replyStatus.textContent = "Write a message first.";
                  return;
                }}
                sendButton.disabled = true;
                replyStatus.textContent = "Sending...";
                try {{
                  const response = await fetch("/chat", {{
                    method: "POST",
                    headers: {{
                      "Content-Type": "application/json",
                    }},
                    body: JSON.stringify({{
                      message,
                      mode: "chat",
                    }}),
                  }});
                  const data = await response.json();
                  if (!response.ok) {{
                    throw new Error(data.detail || "Chat request failed.");
                  }}
                  setAnswer(data.content);
                  replyStatus.textContent = "Nano answered.";
                  await playVoice(data.content);
                  messageBox.value = "";
                }} catch (error) {{
                  replyStatus.textContent = error.message;
                }} finally {{
                  sendButton.disabled = false;
                }}
              }}

              sendButton.addEventListener("click", sendMessage);
              stopAudioButton.addEventListener("click", () => {{
                stopVoicePlayback();
              }});
              copyAnswerButton.addEventListener("click", async () => {{
                try {{
                  await navigator.clipboard.writeText(answerOutput.textContent);
                  copyAnswerButton.textContent = "Copied";
                  setTimeout(() => {{
                    copyAnswerButton.textContent = "Copy Answer";
                  }}, 1200);
                }} catch (error) {{
                  replyStatus.textContent = "Could not copy the answer.";
                }}
              }});
              messageBox.addEventListener("keydown", (event) => {{
                if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {{
                  sendMessage();
                }}
              }});
              brainsPanel.addEventListener("toggle", () => {{
                brainsStatus.textContent = brainsPanel.open ? "open" : "sealed";
              }});

              setAnswer("");
              bootstrap();
              listen();
            </script>
          </body>
        </html>
        """
    ).strip()
