/* Render a small Markdown subset without interpreting model output as HTML. */
function renderAnswer(text, translate = value => value, doc = document) {
  const el = (tag, value) => {
    const result = doc.createElement(tag);
    if (value !== undefined) result.textContent = value;
    return result;
  };
  function inline(target, value) {
    const pattern = /(`[^`\n]+`|\*\*[^*\n]+\*\*|\[[^\]\n]+\]\(https?:\/\/[^\s)]+\))/g;
    let offset = 0;
    for (const match of value.matchAll(pattern)) {
      target.append(doc.createTextNode(value.slice(offset, match.index)));
      const part = match[0];
      if (part.startsWith('`')) target.append(el('code', part.slice(1, -1)));
      else if (part.startsWith('**')) target.append(el('strong', part.slice(2, -2)));
      else {
        const split = part.indexOf(']('), link = el('a', part.slice(1, split));
        link.href = part.slice(split + 2, -1); link.target = '_blank'; link.rel = 'noopener noreferrer';
        target.append(link);
      }
      offset = match.index + part.length;
    }
    target.append(doc.createTextNode(value.slice(offset)));
  }
  const root = el('div'); root.className = 'prose';
  const data = el('details'); data.className = 'discussion-data';
  data.append(el('summary', translate('Discussion data')));
  let dataCount = 0;
  const lines = String(text || '').replaceAll('\r\n', '\n').split('\n');
  const cells = line => line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(cell => cell.trim());
  for (let i = 0; i < lines.length;) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    const fence = line.match(/^\s*(`{3,}|~{3,})(.*)$/);
    if (fence) {
      const content = [], marker = fence[1], label = fence[2].trim(); i++;
      while (i < lines.length && !new RegExp(`^\\s*${marker[0]}{${marker.length},}\\s*$`).test(lines[i])) content.push(lines[i++]);
      const closed = i < lines.length;
      if (closed) i++;
      const pre = el('pre'); pre.append(el('code', content.join('\n')));
      const known = ['agora-issues', 'agora-attributions', 'agora-calculations', 'agora-sources', 'agora-source-reviews', 'agora-result'].includes(label);
      let parsed = false;
      if (known && closed) {
        try { const value = JSON.parse(content.join('\n')); parsed = value !== null && typeof value === 'object'; } catch (_) { /* Keep malformed data visible. */ }
      }
      if (parsed) { data.append(el('h4', label), pre); dataCount++; }
      else {
        if (known) root.append(el('p', translate('This discussion data could not be read. Its original content is shown below.')));
        root.append(pre);
      }
      continue;
    }
    if (line.includes('|') && i + 1 < lines.length && cells(lines[i + 1]).every(cell => /^:?-{3,}:?$/.test(cell))) {
      const scroll = el('div'); scroll.className = 'table-scroll';
      const table = el('table'), head = el('thead'), row = el('tr');
      for (const value of cells(line)) { const cell = el('th'); inline(cell, value); row.append(cell); }
      head.append(row); table.append(head); i += 2;
      const body = el('tbody');
      while (i < lines.length && lines[i].includes('|') && lines[i].trim()) {
        const row = el('tr');
        for (const value of cells(lines[i++])) { const cell = el('td'); inline(cell, value); row.append(cell); }
        body.append(row);
      }
      table.append(body); scroll.append(table); root.append(scroll); continue;
    }
    const heading = line.match(/^(#{1,6})\s+(.+)$/);
    if (heading) { const item = el(`h${Math.min(heading[1].length + 1, 6)}`); inline(item, heading[2]); root.append(item); i++; continue; }
    if (/^\s*([-*_])(?:\s*\1){2,}\s*$/.test(line)) { root.append(el('hr')); i++; continue; }
    const list = line.match(/^\s*(?:([-+*])|(\d+)[.)])\s+(.+)$/);
    if (list) {
      const ordered = !!list[2], block = el(ordered ? 'ol' : 'ul');
      if (ordered) block.start = Number(list[2]);
      while (i < lines.length) {
        const next = lines[i].match(/^\s*(?:([-+*])|(\d+)[.)])\s+(.+)$/);
        if (!next || !!next[2] !== ordered) break;
        const item = el('li'); inline(item, next[3]); block.append(item); i++;
      }
      root.append(block); continue;
    }
    const block = el(line.startsWith('> ') ? 'blockquote' : 'p');
    inline(block, line.startsWith('> ') ? line.slice(2) : line); root.append(block); i++;
  }
  if (dataCount) root.append(data);
  const source = el('details'); source.className = 'source-text';
  source.append(el('summary', translate('Source text')), el('pre', text || '')); root.append(source);
  return root;
}
if (typeof module !== 'undefined') module.exports = {renderAnswer};
