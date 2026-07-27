const HOME_SCRIPT_ORDER = [
  "home-state.js",
  "home-plans.js",
  "home-calendar.js",
  "home-ui.js",
  "home-view-session.js",
  "home-voice.js",
  "home-activity.js",
  "home-chat.js",
  "home-bootstrap.js",
];

function loadClassicScript(src) {
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = `${src.split("?")[0]}?v=module-entry-5`;
    script.async = false;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error(`Failed to load ${src}`));
    document.head.appendChild(script);
  });
}

for (const file of HOME_SCRIPT_ORDER) {
  await loadClassicScript(`/static/${file}?v=module-entry-5`);
}
