const AgoraDiscussion = (() => {
  function shortTitle(question, limit = 78) {
    const text = String(question || '').replace(/\s+/g, ' ').trim();
    return text.length > limit ? text.slice(0, limit).trimEnd() + '…' : text;
  }
  const resultInstruction = '\nIn each initial and review answer, append exactly one fenced agora-position JSON array with exactly one object containing disposition (ready, blocked, conditional, user_choice, or undetermined), conclusion (1-600 characters), and conditions (1-4 strings of 1-500 characters each). Describe your own current answer to the original question. Use ready only for an unconditional supported choice, blocked when a mandatory requirement prevents proceeding, conditional for if/then guidance, user_choice when only preferences remain, and undetermined when no position can be formed. Keep the same meaning as your prose and write in the requested language. Do not declare another participant\'s position. The summary must not emit agora-position. In the summary only, append exactly one fenced agora-result JSON object with version: 1, conclusion: a plain-text string (1-600 characters), conditions: 1-4 plain-text strings, reasons: 1-3 plain-text strings, and next_steps: 0-3 plain-text strings. Each list item must be 1-500 characters. Make each item one short sentence. This is a concise presentation of the same conclusion, not a new decision. Keep material assumptions, unresolved disagreements, uncertainty, and constraints that change the recommendation in conditions. Do not omit them just to be brief. Keep turn IDs, speaker attribution, and discussion mechanics in the full synthesis, not these fields. Use the language explicitly requested by the user, otherwise the language of the question, for every user-facing field and the full synthesis; do not switch languages when summarizing. Also include answer_state (complete, conditional, or incomplete) and decision_state (ready, user_choice, missing_facts, conflicting_evidence, or unresolved_disagreement). These are your reported assessments, not verification or authorization. A complete conditional explanation may still have a blocked decision. Mandatory unknowns and conflicting evidence take precedence over preferences; retain all other blockers in conditions. Include the specific conflicting values or claims in conditions when evidence conflicts. Still include the full synthesis and the other required evidence blocks. Do not claim agreement is factual verification.';
  const decisionInstruction = '\nHelp the user decide under their stated constraints, not merely reach agreement. Separate facts, assumptions, hard constraints, and preferences. Preserve useful conditional advice when there is no single best choice. Do not invent preferences or let preferences override factual prerequisites. For new summaries add clarification: null, or an object with exactly question (1-300 characters) and why (1-300 characters). Ask at most one focused question whose answer would materially change the recommendation or next action, only when not already answered. Explain that dependency in why. Use null when the user requested conditional advice that can already be completed, or no useful question remains. A missing factual prerequisite takes priority over preferences: ask for relevant evidence if the user can supply it, never ask which conflicting fact they prefer. Do not bundle several questions. A user report is not independently verified evidence. In a follow-up, use new information to revise the relevant recommendation and retain any unresolved conditions. Use the requested language for question and why.';
  function resultCard(text) {
    const blocks = [...String(text || '').matchAll(/^```agora-result[ \t]*\r?\n([\s\S]*?)^```[ \t]*\r?$/gm)];
    if (blocks.length !== 1) return null;
    try {
      const value = JSON.parse(blocks[0][1]);
      const line = (item, limit) => typeof item === 'string' && item.trim().length > 0 && item.length <= limit;
      const list = (items, min, max) => Array.isArray(items) && items.length >= min && items.length <= max && items.every(item => line(item, 500));
      if (!value || Object.keys(value).some(key => !['version', 'conclusion', 'conditions', 'reasons', 'next_steps', 'answer_state', 'decision_state', 'clarification'].includes(key)) || value.version !== 1 || !line(value.conclusion, 600) || !list(value.conditions, 1, 4)
          || !list(value.reasons, 1, 3) || !list(value.next_steps, 0, 3)) return null;
      const states = {};
      if ('clarification' in value) {
        const question = value.clarification;
        if (question !== null && (!question || Array.isArray(question) || Object.keys(question).sort().join(',') !== 'question,why' || !line(question.question, 300) || !line(question.why, 300))) return null;
        states.clarification = question;
      }
      if ('answer_state' in value || 'decision_state' in value) {
        if (!['complete', 'conditional', 'incomplete'].includes(value.answer_state) || !['ready', 'user_choice', 'missing_facts', 'conflicting_evidence', 'unresolved_disagreement'].includes(value.decision_state)) return null;
        states.answer_state = value.answer_state; states.decision_state = value.decision_state;
      }
      return {...states, conclusion: value.conclusion, conditions: value.conditions, reasons: value.reasons, next_steps: value.next_steps};
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
  return {shortTitle, excerpt, issueGroups, rounds, stages, activity, purposes, purposeRules, checksFor, resultCard, resultInstruction: resultInstruction + decisionInstruction};
})();
if (typeof module !== 'undefined') module.exports = AgoraDiscussion;
