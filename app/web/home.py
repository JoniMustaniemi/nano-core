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
                --bg: #081019;
                --panel: rgba(12, 20, 32, 0.88);
                --panel-border: rgba(151, 191, 158, 0.18);
                --text: #e8f4ea;
                --muted: #9cb4a3;
                --accent: #76d39b;
                --accent-strong: #98f0bb;
                --warning: #f4c15d;
                --error: #ff8a7a;
                --shadow: 0 20px 60px rgba(0, 0, 0, 0.35);
              }}
              * {{ box-sizing: border-box; }}
              body {{
                margin: 0;
                min-height: 100vh;
                font-family: Inter, "Segoe UI", system-ui, sans-serif;
                color: var(--text);
                background:
                  radial-gradient(circle at top left, rgba(118, 211, 155, 0.18), transparent 28%),
                  radial-gradient(circle at top right, rgba(53, 130, 97, 0.18), transparent 24%),
                  linear-gradient(180deg, #071018 0%, #0a1320 52%, #04070b 100%);
              }}
              .shell {{
                width: min(1080px, calc(100vw - 32px));
                margin: 0 auto;
                padding: 32px 0 48px;
              }}
              .hero {{
                display: grid;
                gap: 12px;
                margin-bottom: 24px;
              }}
              .eyebrow {{
                color: var(--accent);
                text-transform: uppercase;
                letter-spacing: 0.22em;
                font-size: 12px;
                font-weight: 700;
              }}
              h1 {{
                margin: 0;
                font-size: clamp(2.5rem, 7vw, 5.2rem);
                line-height: 0.95;
                letter-spacing: -0.05em;
              }}
              .subhead {{
                margin: 0;
                max-width: 64ch;
                color: var(--muted);
                font-size: 1rem;
                line-height: 1.6;
              }}
              .grid {{
                display: grid;
                grid-template-columns: minmax(0, 1.25fr) minmax(320px, 0.75fr);
                gap: 20px;
              }}
              .card {{
                border: 1px solid var(--panel-border);
                border-radius: 24px;
                background: var(--panel);
                box-shadow: var(--shadow);
                backdrop-filter: blur(18px);
              }}
              .status-card {{
                padding: 24px;
                display: grid;
                gap: 18px;
              }}
              .status-row {{
                display: flex;
                flex-wrap: wrap;
                align-items: center;
                gap: 12px;
              }}
              .pill {{
                display: inline-flex;
                align-items: center;
                gap: 8px;
                border-radius: 999px;
                padding: 10px 14px;
                border: 1px solid rgba(118, 211, 155, 0.25);
                background: rgba(118, 211, 155, 0.12);
                color: var(--accent-strong);
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                font-size: 0.75rem;
              }}
              .dot {{
                width: 10px;
                height: 10px;
                border-radius: 50%;
                background: var(--accent);
                box-shadow: 0 0 0 6px rgba(118, 211, 155, 0.12);
              }}
              .status-state {{
                margin: 0;
                font-size: clamp(1.4rem, 3vw, 2.2rem);
                letter-spacing: -0.03em;
              }}
              .status-detail {{
                margin: 0;
                color: var(--muted);
                line-height: 1.6;
              }}
              .composer {{
                display: grid;
                gap: 12px;
                padding: 24px;
              }}
              .composer label {{
                font-weight: 600;
                color: var(--muted);
              }}
              textarea {{
                width: 100%;
                min-height: 120px;
                resize: vertical;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 18px;
                padding: 14px 16px;
                background: rgba(3, 8, 14, 0.72);
                color: var(--text);
                font: inherit;
                outline: none;
              }}
              textarea:focus {{
                border-color: rgba(118, 211, 155, 0.5);
                box-shadow: 0 0 0 4px rgba(118, 211, 155, 0.12);
              }}
              button {{
                justify-self: start;
                border: 0;
                border-radius: 999px;
                padding: 12px 18px;
                background: linear-gradient(135deg, var(--accent), var(--accent-strong));
                color: #06110b;
                font-weight: 800;
                cursor: pointer;
              }}
              button:disabled {{
                opacity: 0.55;
                cursor: wait;
              }}
              .feed {{
                margin-top: 20px;
                padding: 24px;
              }}
              .memory {{
                margin-top: 20px;
                padding: 24px;
                display: grid;
                gap: 18px;
              }}
              .memory-grid {{
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 18px;
              }}
              .memory h2 {{
                margin: 0;
                font-size: 1.1rem;
              }}
              .memory h3 {{
                margin: 0 0 12px;
                font-size: 0.95rem;
                color: var(--accent-strong);
                letter-spacing: 0.06em;
                text-transform: uppercase;
              }}
              .memory-list {{
                list-style: none;
                margin: 0;
                padding: 0;
                display: grid;
                gap: 10px;
              }}
              .memory-item {{
                padding: 12px 14px;
                border-radius: 14px;
                background: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.06);
              }}
              .feed h2 {{
                margin: 0 0 14px;
                font-size: 1.1rem;
              }}
              .events {{
                list-style: none;
                margin: 0;
                padding: 0;
                display: grid;
                gap: 12px;
              }}
              .event {{
                padding: 14px 16px;
                border-radius: 16px;
                background: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.06);
              }}
              .event-top {{
                display: flex;
                justify-content: space-between;
                gap: 12px;
                align-items: center;
                margin-bottom: 6px;
              }}
              .event-title {{
                font-weight: 700;
              }}
              .event-meta {{
                color: var(--muted);
                font-size: 0.85rem;
              }}
              .event-detail {{
                margin: 0;
                color: var(--muted);
                line-height: 1.5;
              }}
              .message {{
                margin: 0;
                color: var(--warning);
                min-height: 1.4em;
              }}
              @media (max-width: 900px) {{
                .grid {{
                  grid-template-columns: 1fr;
                }}
              }}
            </style>
          </head>
          <body>
            <main class="shell">
              <section class="hero">
                <div class="eyebrow">{app_name}</div>
              </section>

              <section class="grid">
                <div class="card status-card">
                  <div class="status-row">
                    <span id="state-pill" class="pill">
                      <span class="dot"></span><span id="state-label">standby</span>
                    </span>
                    <span class="event-meta" id="updated-at">waiting for status...</span>
                  </div>
                  <div>
                    <h2 class="status-state" id="headline">Nano is in standby.</h2>
                    <p class="status-detail" id="detail">Ready for the next task.</p>
                  </div>
                </div>

                <div class="card composer">
                  <label for="message">Try a chat action</label>
                  <textarea
                    id="message"
                    placeholder="Ask Nano something, and watch the status change while it works."
                  ></textarea>
                  <button id="send" type="button">Send to Nano</button>
                  <p class="message" id="reply"></p>
                </div>
              </section>

              <section class="card feed">
                <h2>Recent activity</h2>
                <ul id="events" class="events"></ul>
              </section>

              <section class="card memory">
                <h2>Database memory</h2>
                <div class="memory-grid">
                  <div>
                    <h3>Notes</h3>
                    <ul id="notes" class="memory-list"></ul>
                  </div>
                  <div>
                    <h3>Reminders</h3>
                    <ul id="reminders" class="memory-list"></ul>
                  </div>
                </div>
              </section>
            </main>

            <script>
              const stateLabel = document.getElementById("state-label");
              const headline = document.getElementById("headline");
              const detail = document.getElementById("detail");
              const updatedAt = document.getElementById("updated-at");
              const eventsList = document.getElementById("events");
              const notesList = document.getElementById("notes");
              const remindersList = document.getElementById("reminders");
              const reply = document.getElementById("reply");
              const messageBox = document.getElementById("message");
              const sendButton = document.getElementById("send");

              const stateStyles = {{
                standby: {{
                  pill: "rgba(118, 211, 155, 0.12)",
                  border: "rgba(118, 211, 155, 0.25)",
                  text: "#98f0bb",
                  dot: "#76d39b",
                }},
                working: {{
                  pill: "rgba(244, 193, 93, 0.12)",
                  border: "rgba(244, 193, 93, 0.25)",
                  text: "#f4c15d",
                  dot: "#f4c15d",
                }},
                error: {{
                  pill: "rgba(255, 138, 122, 0.12)",
                  border: "rgba(255, 138, 122, 0.25)",
                  text: "#ff8a7a",
                  dot: "#ff8a7a",
                }},
              }};

              function formatTime(value) {{
                if (!value) {{
                  return "waiting for status...";
                }}
                return new Date(value).toLocaleString();
              }}

              function applyState(snapshot) {{
                const state = snapshot.state || "standby";
                const styles = stateStyles[state] || stateStyles.standby;
                const pill = document.getElementById("state-pill");
                pill.style.background = styles.pill;
                pill.style.borderColor = styles.border;
                pill.style.color = styles.text;
                pill.querySelector(".dot").style.background = styles.dot;

                stateLabel.textContent = state;
                headline.textContent = snapshot.headline || "Nano is in standby.";
                detail.textContent = snapshot.detail || "";
                updatedAt.textContent = `Updated ${{formatTime(snapshot.updated_at)}}`;
              }}

              function renderEvent(event) {{
                const item = document.createElement("li");
                item.className = "event";
                const stamp = event.created_at
                  ? new Date(event.created_at).toLocaleTimeString()
                  : "";
                item.innerHTML = `
                  <div class="event-top">
                    <span class="event-title">${{event.title || "Activity"}}</span>
                    <span class="event-meta">
                      ${{event.source || "system"}}${{stamp ? " | " + stamp : ""}}
                    </span>
                  </div>
                  <p class="event-detail">${{event.detail || event.state || ""}}</p>
                `;
                eventsList.prepend(item);
                while (eventsList.children.length > 8) {{
                  eventsList.removeChild(eventsList.lastChild);
                }}
              }}

              function refreshEvents(snapshot) {{
                eventsList.innerHTML = "";
                const events = Array.isArray(snapshot.events)
                  ? snapshot.events.slice().reverse()
                  : [];
                for (const event of events) {{
                  renderEvent(event);
                }}
              }}

              function renderMemoryList(list, items, emptyLabel) {{
                list.innerHTML = "";
                if (!items.length) {{
                  const empty = document.createElement("li");
                  empty.className = "memory-item";
                  empty.textContent = emptyLabel;
                  list.appendChild(empty);
                  return;
                }}
                for (const item of items) {{
                  const entry = document.createElement("li");
                  entry.className = "memory-item";
                  entry.textContent = item;
                  list.appendChild(entry);
                }}
              }}

              async function loadMemory() {{
                const [notesResponse, remindersResponse] = await Promise.all([
                  fetch("/api/notes"),
                  fetch("/api/reminders"),
                ]);
                const notes = notesResponse.ok ? await notesResponse.json() : [];
                const reminders = remindersResponse.ok ? await remindersResponse.json() : [];
                renderMemoryList(
                  notesList,
                  notes.map((note) => note.content),
                  "No notes yet.",
                );
                renderMemoryList(
                  remindersList,
                  reminders.map((reminder) => reminder.content),
                  "No reminders yet.",
                );
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
                  await loadMemory();
                }} catch (error) {{
                  reply.textContent = error.message;
                }}
              }}

              function listen() {{
                const source = new EventSource("/events");
                source.addEventListener("activity", (event) => {{
                  const payload = JSON.parse(event.data);
                  const snapshot = {{
                    state: payload.state,
                    headline: payload.title,
                    detail: payload.detail,
                    updated_at: payload.created_at,
                  }};
                  applyState(snapshot);
                  renderEvent(payload);
                }});
                source.onerror = () => {{
                  updatedAt.textContent = "Live stream reconnecting...";
                }};
              }}

              async function sendMessage() {{
                const message = messageBox.value.trim();
                if (!message) {{
                  reply.textContent = "Write a message first.";
                  return;
                }}
                sendButton.disabled = true;
                reply.textContent = "Sending...";
                try {{
                  const response = await fetch("/chat", {{
                    method: "POST",
                    headers: {{
                      "Content-Type": "application/json",
                    }},
                    body: JSON.stringify({{ message }}),
                  }});
                  const data = await response.json();
                  if (!response.ok) {{
                    throw new Error(data.detail || "Chat request failed.");
                  }}
                  reply.textContent = data.content;
                  messageBox.value = "";
                }} catch (error) {{
                  reply.textContent = error.message;
                }} finally {{
                  sendButton.disabled = false;
                }}
              }}

              document.getElementById("send").addEventListener("click", sendMessage);
              messageBox.addEventListener("keydown", (event) => {{
                if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {{
                  sendMessage();
                }}
              }});

              bootstrap();
              listen();
            </script>
          </body>
        </html>
        """
    ).strip()
