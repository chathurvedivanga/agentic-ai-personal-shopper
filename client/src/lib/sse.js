export function consumeSseEvents(buffer) {
  const normalized = buffer.replace(/\r\n/g, "\n");
  const blocks = normalized.split("\n\n");
  const remainder = blocks.pop() ?? "";

  const events = blocks
    .map((block) => parseEventBlock(block))
    .filter(Boolean);

  return { events, remainder };
}

function parseEventBlock(block) {
  let event = "message";
  const dataLines = [];

  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
      continue;
    }

    if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }

  if (!dataLines.length) {
    return null;
  }

  return {
    event,
    data: dataLines.join("\n")
  };
}

export function parseJsonPayload(rawData) {
  try {
    return JSON.parse(rawData);
  } catch {
    return { message: rawData };
  }
}
