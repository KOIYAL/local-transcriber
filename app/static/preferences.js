// Desktop ports change between launches. Persist through Electron when present.
// Retain session values if disk/browser storage is unavailable.
(() => {
  const session = new Map();
  window.LTPreferences = {
    get(key) {
      if (session.has(key)) return session.get(key);
      try {
        return window.localTranscriber?.settings
          ? window.localTranscriber.settings.get(key) : window.localStorage.getItem(key);
      } catch {
        return null;
      }
    },
    set(key, value) {
      session.set(key, value);
      try {
        if (window.localTranscriber?.settings) window.localTranscriber.settings.set(key, value);
        else if (value === null) window.localStorage.removeItem(key);
        else window.localStorage.setItem(key, value);
      } catch {
        // Controls remain usable for this session.
      }
    },
  };
})();
