const AgoraDiscussion = (() => {
  function shortTitle(question, limit = 78) {
    const text = String(question || '').replace(/\s+/g, ' ').trim();
    return text.length > limit ? text.slice(0, limit).trimEnd() + '…' : text;
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
  return {shortTitle, excerpt, issueGroups, rounds, stages, activity, purposes, purposeRules, checksFor};
})();
if (typeof module !== 'undefined') module.exports = AgoraDiscussion;
