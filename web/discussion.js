const AgoraDiscussion = (() => {
  function shortTitle(question, limit = 78) {
    const text = String(question || '').replace(/\s+/g, ' ').trim();
    return text.length > limit ? text.slice(0, limit).trimEnd() + '…' : text;
  }
  const resultInstruction = '\nIn the summary only, append exactly one fenced agora-result JSON object with version: 1, conclusion: a plain-text string (1-600 characters), conditions: 1-4 plain-text strings, reasons: 1-3 plain-text strings, and next_steps: 0-3 plain-text strings. Each list item must be 1-500 characters. Make each item one short sentence. This is a concise presentation of the same conclusion, not a new decision. Keep material assumptions, unresolved disagreements, uncertainty, and constraints that change the recommendation in conditions. Do not omit them just to be brief. Keep turn IDs, speaker attribution, and discussion mechanics in the full synthesis, not these fields. Use the language explicitly requested by the user, otherwise the language of the question, for every user-facing field and the full synthesis; do not switch languages when summarizing. Still include the full synthesis and the other required evidence blocks. Do not claim agreement is factual verification.';
  function resultCard(text) {
    const blocks = [...String(text || '').matchAll(/^```agora-result[ \t]*\r?\n([\s\S]*?)^```[ \t]*\r?$/gm)];
    if (blocks.length !== 1) return null;
    try {
      const value = JSON.parse(blocks[0][1]);
      const line = (item, limit) => typeof item === 'string' && item.trim().length > 0 && item.length <= limit;
      const list = (items, min, max) => Array.isArray(items) && items.length >= min && items.length <= max && items.every(item => line(item, 500));
      if (!value || Object.keys(value).some(key => !['version', 'conclusion', 'conditions', 'reasons', 'next_steps'].includes(key)) || value.version !== 1 || !line(value.conclusion, 600) || !list(value.conditions, 1, 4)
          || !list(value.reasons, 1, 3) || !list(value.next_steps, 0, 3)) return null;
      return {conclusion: value.conclusion, conditions: value.conditions, reasons: value.reasons, next_steps: value.next_steps};
    } catch (_) { return null; }
  }
  function excerpt(text) {
    const prose = String(text || '').split('```')[0].replace(/^#{1,6}\s+/gm, '').replace(/\*\*|`/g, '');
    return shortTitle(prose, 230);
  }
  function issueGroups(issues = []) {
    return {
      agreed: issues.filter(issue => issue.status === 'agreed'),
      open: issues.filter(issue => issue.status !== 'agreed')
    };
  }
  function rounds(turns = []) {
    const groups = new Map();
    turns.forEach((turn, index) => {
      if (turn.phase === 'summary') return;
      const key = turn.phase === 'initial' ? 0 : turn.round;
      if (!groups.has(key)) groups.set(key, {round: key, turns: []});
      groups.get(key).turns.push({...turn, index, id: `T${String(index + 1).padStart(3, '0')}`});
    });
    return [...groups.values()];
  }
  function stages(record) {
    const turns = record.turns || [];
    const both = list => ['codex', 'claude'].every(provider => list.some(turn => turn.provider === provider));
    return [
      both(turns.filter(turn => turn.phase === 'initial')),
      Array.from({length: record.rounds}, (_, i) => i + 1).every(round =>
        both(turns.filter(turn => turn.phase === 'review' && turn.round === round))),
      turns.some(turn => turn.phase === 'summary')
    ];
  }
  const purposes = {
    general: '',
    decision: 'Compare the feasible choices against explicit criteria. State assumptions, tradeoffs, and what would change the recommendation. Leave the final decision to the user.',
    verify: 'Break the claim into checkable parts. Separate supporting evidence, counterevidence, and missing evidence. Do not treat model agreement as verification.',
    compare: 'Compare alternatives using the same criteria. Describe tradeoffs and conditions under which each alternative is preferable. Do not invent missing facts.'
  };
  function purposeRules(rules, purpose) {
    return purposes[purpose] ? `${rules}\n\nDiscussion purpose: ${purpose}. ${purposes[purpose]}` : rules;
  }
  function checksFor(record, turnId) {
    const number = Number(String(turnId).slice(1));
    return {
      calculations: (record.calculation_checks || []).filter(row => row.turn === number).flatMap(row => row.checks || []),
      sources: (record.source_checks || []).filter(row => row.turn === number).flatMap(row => row.checks || []),
      responses: (record.attribution_checks || []).flatMap(row => row.checks || []).filter(check =>
        check.turn_id === turnId && check.responds_to && check.status === 'quote_and_context_match')
    };
  }
  function activity(phase) {
    const [provider, step] = String(phase || '').split(': ');
    return {provider, step: ['initial', 'review', 'summary'].includes(step) ? step : 'preparing'};
  }
  return {shortTitle, excerpt, issueGroups, rounds, stages, activity, purposes, purposeRules, checksFor, resultCard, resultInstruction};
})();
if (typeof module !== 'undefined') module.exports = AgoraDiscussion;
