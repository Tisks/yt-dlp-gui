const URL_ENDPOINT = "http://127.0.0.1:5005/url";

chrome.commands.onCommand.addListener((command) => {
  if (command === "send-url") {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const url = tabs[0]?.url;
      if (!url) return;

      fetch(URL_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      }).catch(() => {});
    });
  }
});
