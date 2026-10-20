import assert from 'node:assert/strict';
import { test } from 'node:test';
import { comparisonHintBlockReason, personalComparisonMarkup } from '../foreman_web/app.js';

const base = () => ({
  protocol: { id: 'local', version: 'v2', contentVersion: 'draft.2', analysisUnit: 'one learner', contentReviewStatus: 'candidate' },
  enrolled: false, priorConceptExposure: false, status: 'insufficient_evidence',
  reason: 'Four dependent units cannot establish benefit.', uncertainty: 'No interval.',
  units: [], arms: {}, descriptive: {}, next: null, instruction: null, question: null, feedback: null,
});

test('enrollment is prospective and prior history is shown as a blocker', () => {
  const report = base();
  assert.match(personalComparisonMarkup(report), /Start this draft comparison/);
  report.priorConceptExposure = true;
  const html = personalComparisonMarkup(report);
  assert.doesNotMatch(html, /id="comparison-enroll"/);
  assert.match(html, /Your existing history stays as it is/);
});

test('worked answer remains behind explicit exposure start and assigned diagram', () => {
  const report = base(); report.enrolled = true;
  report.units = [{id:'u1', name:'A', condition:'diagram', exposureStartedAt:null}];
  report.next = {unitId:'u1',stage:'study'};
  assert.match(personalComparisonMarkup(report), /Open the worked example/);
  report.instruction = {workedCode:'x < 3',workedAnswer:'3, 9',steps:['First < step'],
    misconceptions:['Wrong < idea'],diagram:'x -> 3',studyTargetMinutes:10,source:'https://docs.python.org/'};
  assert.doesNotMatch(personalComparisonMarkup(report), /First &lt; step/);
  assert.match(personalComparisonMarkup(report), /Open the worked example/);
  report.units[0].exposureStartedAt = '2026-10-18T12:00:00Z';
  const html = personalComparisonMarkup(report);
  assert.match(html, /First &lt; step/);
  assert.match(html, /Labeled diagram/);
  assert.match(html, /I studied this worked example/);
  assert.match(html, /Before this lesson, had you studied this topic outside Aesop/);
});

test('delayed question exposes no answer and feedback labels draft and assistance', () => {
  const report = base(); report.enrolled = true;
  report.next = {unitId:'u1',stage:'delayed'};
  report.question = {phase:'delayed',prompt:'Trace this',code:'x = 1',familyId:'held-out',hintAvailable:false,hintOpened:false};
  let html = personalComparisonMarkup(report, '', new Date(), true);
  assert.match(html, /Unfamiliar later check/);
  assert.match(html, /Since the worked example, have you studied this topic outside Aesop/);
  assert.doesNotMatch(html, /Open practice hint/);
  assert.doesNotMatch(html, /Draft answer:/);
  report.feedback = {phase:'practice',candidateMatch:true,assisted:true,answer:'3, 9',steps:['Reason']};
  html = personalComparisonMarkup(report);
  assert.match(html, /Feedback from the earlier answer stays hidden while the later check is ready/);
  assert.doesNotMatch(html, /Show the draft answer and the steps/);
  report.next = {unitId:'u2',stage:'study'};
  report.question = null;
  report.units = [{id:'u2',name:'B',condition:'text',exposureStartedAt:null}];
  html = personalComparisonMarkup(report);
  assert.match(html, /assisted practice/);
  assert.match(html, /Show the draft answer and the steps/);
  assert.match(html, /id="comparison-reveal"/);
  assert.doesNotMatch(html, /Draft answer: <strong>3, 9/);
  report.feedback.assisted = false;
  html = personalComparisonMarkup(report);
  assert.match(html, /unassisted response\. Whether the later check counts is reported separately/);
  assert.doesNotMatch(html, /independent answer/);
});

test('solution exposure is distinguished from the locked first answer', () => {
  const report = base(); report.enrolled = true;
  report.units = [{id:'u1',name:'A',condition:'text',practiceAnswered:true,
    practiceAssisted:false,practiceCandidateMatch:true,classification:'missing',
    practiceSolutionRevealedAt:null,delayedSolutionRevealedAt:null}];
  report.feedback = {unitId:'u1',phase:'practice',candidateMatch:true,assisted:false,
    answer:'3, 9',steps:['Reason'],solutionRevealedAt:null};
  let html = personalComparisonMarkup(report);
  assert.match(html, /The time you opened this answer is not recorded/);
  assert.match(html, /<th scope="col">Answer opened<\/th>/);
  assert.match(html, /Unassisted\. No hint was used/);
  assert.doesNotMatch(html, /Draft answer: <strong>3, 9/);
  report.units[0].practiceSolutionRevealedAt = '2026-10-18T12:00:00Z';
  report.feedback.solutionRevealedAt = report.units[0].practiceSolutionRevealedAt;
  html = personalComparisonMarkup(report);
  assert.match(html, /The time you opened this answer is recorded/);
  assert.match(html, /Draft answer: <strong>3, 9/);
  assert.match(html, /data-solution-unit="u1">Opened during practice<\/td>/);
  report.units[0].practiceSolutionRevealedAt = null;
  report.units[0].delayedSolutionRevealedAt = '2026-10-26T12:00:00Z';
  assert.match(personalComparisonMarkup(report), /data-solution-unit="u1">Opened during the later check<\/td>/);
});

test('historical comparison does not imply its solution openings were observed', () => {
  const report = base(); report.enrolled = true; report.protocol.version = 'v1';
  report.units = [{id:'u1',name:'A',condition:'text',classification:'missing'}];
  report.feedback = {phase:'practice',candidateMatch:false,assisted:false,
    answer:'3, 9',steps:['Reason']};
  const html = personalComparisonMarkup(report);
  assert.match(html, /This older version did not record when the answer was opened/);
});

test('opened delayed family loses unfamiliar label and warns after 30 minutes', () => {
  const report = base(); report.enrolled = true;
  report.next = {unitId:'u1',stage:'delayed'};
  report.question = {phase:'delayed',prompt:'Trace this',code:'x = 1',familyId:'held-out',hintAvailable:false,hintOpened:false};
  report.units = [{id:'u1',name:'A',condition:'text',delayedFirstViewedAt:null}];
  const now = new Date('2026-10-18T12:31:00Z');
  assert.match(personalComparisonMarkup(report, '', now, true), /Unfamiliar later check/);
  report.units[0].delayedFirstViewedAt = '2026-10-18T12:00:00Z';
  const html = personalComparisonMarkup(report, '', now);
  assert.match(html, /Later check already opened/);
  assert.doesNotMatch(html, /Unfamiliar later check/);
  assert.match(personalComparisonMarkup(report, '', now, true), /Unfamiliar later check/);
  assert.match(html, /classified contaminated/);
  assert.doesNotMatch(personalComparisonMarkup(report, '', new Date('2026-10-18T12:29:00Z')), /classified contaminated/);
});

test('a typed first answer blocks hint; hint-opened practice uses assisted wording', () => {
  assert.match(comparisonHintBlockReason('12, 40'), /Submit it as your unassisted first answer/);
  assert.equal(comparisonHintBlockReason('   '), null);
  const report = base(); report.enrolled = true;
  report.next = {unitId:'u1',stage:'practice'};
  report.question = {phase:'practice',prompt:'Trace',code:'x = 1',familyId:'practice-a',hintAvailable:true,hintOpened:false};
  let html = personalComparisonMarkup(report);
  assert.match(html, /Open a hint only while the answer field is blank/);
  assert.match(html, /Before this answer, have you studied this topic outside Aesop/);
  assert.match(html, /unassisted first answer/);
  report.question.hintAvailable = false;
  report.question.hintOpened = true;
  report.question.hintLevel = 2;
  report.question.hintText = 'Trace each statement in order.';
  html = personalComparisonMarkup(report);
  assert.match(html, /this answer will be assisted practice/);
  assert.match(html, /Hint 2: Trace each statement in order/);
  assert.doesNotMatch(html, /for an unassisted first answer/);
});

test('first opened hint offers the next step after refresh', () => {
  const report = base(); report.enrolled = true;
  report.next = {unitId:'u1',stage:'practice'};
  report.question = {phase:'practice',prompt:'Trace',code:'x = 1',familyId:'practice-a',
    hintAvailable:true,hintOpened:true,hintLevel:1,hintText:'Identify the local values.'};
  const html = personalComparisonMarkup(report);
  assert.match(html, /Hint 1: Identify the local values/);
  assert.match(html, /Open the next practice hint/);
});

test('arm report visibly counts delayed answers with unknown outside study', () => {
  const report = base(); report.enrolled = true;
  report.arms = {
    text: {assigned:2,eligible:0,provisional:0,missing:1,late:0,contaminated:0,outsideStudyUnknown:1},
    diagram: {assigned:2,eligible:0,provisional:0,missing:2,late:0,contaminated:0,outsideStudyUnknown:0},
  };
  report.descriptive = {text:{observed:1,candidateMatches:1,eligibleCandidateMatches:0},diagram:{observed:0,candidateMatches:0,eligibleCandidateMatches:0}};
  const html = personalComparisonMarkup(report);
  assert.match(html, /<th scope="col">Outside study unknown<\/th>/);
  assert.match(html, /<th scope="col">Eligible draft-key matches<\/th>/);
  assert.match(html, /Columns that say all include answers that do not qualify/);
  assert.match(html, /<th scope="row">Text<\/th>.*<td>1<\/td><\/tr>/);
});

test('versioned suggestion explains evidence and preserves an override choice', () => {
  const report = base(); report.enrolled = true;
  report.next = {unitId:'u1',stage:'delayed'};
  report.recommendation = {policyVersion:'scope-next-v1',unitId:'u1',stage:'delayed',
    reason:'The held-out check is due.',aim:'Observe delayed tracing.',
    evidenceUnitIds:['u1'],uncertainty:'No method winner.',
    alternative:{unitId:'u2',stage:'study'}};
  let html = personalComparisonMarkup(report);
  assert.match(html, /Suggested next: Later check · u1/);
  assert.match(html, /Based on these units:<\/strong> u1/);
  assert.match(html, /Decision rule scope-next-v1/);
  assert.match(html, /id="comparison-override"/);
  report.override = {selectedUnitId:'u2',selectedStage:'study'};
  report.next = {unitId:'u2',stage:'study'};
  html = personalComparisonMarkup(report);
  assert.match(html, /The original suggestion stays recorded/);
  assert.doesNotMatch(html, /id="comparison-override"/);
});

test('dimension panel states missing measures and optional pre-answer confidence', () => {
  const report = base(); report.enrolled = true;
  report.next = {unitId:'u1',stage:'practice'};
  report.question = {phase:'practice',prompt:'Trace',code:'x = 1',familyId:'fresh',hintAvailable:true,hintOpened:false};
  report.dimensions = {explanation:{status:'not_measured',observations:0},
    delayedRetention:{status:'insufficient_evidence',observations:0,
      observationLabel:'eligible unfamiliar delayed responses',otherRecordedResponses:1},
    confidenceCalibration:{status:'candidate_pairs_only',pairs:1,
      interpretation:'No validated calibration estimate.'}};
  const html = personalComparisonMarkup(report);
  assert.match(html, /How sure are you before feedback/);
  assert.match(html, /id="comparison-confidence"/);
  assert.match(html, /explanation:<\/strong> not measured/);
  assert.match(html, /0 eligible unfamiliar delayed responses/);
  assert.match(html, /1 other delayed response kept as description only/);
  assert.match(html, /No validated calibration estimate/);
  assert.match(html, /later check uses what you say at study time and when you return/);
});

test('unknown study declaration explains delayed primary exclusion', () => {
  const report = base(); report.enrolled = true;
  report.units = [{id:'u1',name:'A',condition:'text',exposureStartedAt:'2026-10-18T12:00:00Z'}];
  report.next = {unitId:'u1',stage:'study'};
  report.instruction = {workedCode:'x = 1',workedAnswer:'1, 9',steps:['Trace'],
    misconceptions:[],diagram:null,studyTargetMinutes:10,source:'https://docs.python.org/'};
  const html = personalComparisonMarkup(report);
  assert.match(html, /If this is unknown, or you report some outside study, the answer stays recorded/);
  assert.match(html, /aria-describedby="comparison-outside-note"/);
});
