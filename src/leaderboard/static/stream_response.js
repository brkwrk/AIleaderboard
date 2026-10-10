function update_rows(textarea) {
  textarea.rows = Math.max(1, textarea.value.split("\n").length);
}

function append_text(textarea, text) {
  textarea.textContent += text;
  update_rows(textarea);

  // Scroll the textarea to its newest content.
  textarea.scrollTop = textarea.scrollHeight;

  // page should follow the textarea
  window.scrollTo({ top: document.documentElement.scrollHeight });
}

async function load_content(output, uuid) {
  console.log(`loading character response ${uuid}...`)
  output.textContent = '';
  output.scrollIntoView();

  const response = await fetch(`/character_response/${uuid}`, {
    "method": "GET",
  });

  if (!response.ok) {
    append_text(output, await response.text());
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    append_text(output, decoder.decode(value, { stream: true }));
  }

  // Flush any remaining bytes.
  append_text(output, decoder.decode());

  console.log("action complete");
}

function dom_content_loaded() {
  const response = document.getElementById("response");
  if (!response) {
    console.log("could not find 'response' element.");
    return;
  }
  const uuid = response.textContent;
  if (!uuid) {
    console.log("uuid is empty.");
    return;
  }
  if (uuid.length != 36) {
    console.log(`uuid '${uuid.slice(0, 36)}' is invalid.`);
    return;
  }
  load_content(response, uuid);
}

document.addEventListener("DOMContentLoaded", dom_content_loaded);
