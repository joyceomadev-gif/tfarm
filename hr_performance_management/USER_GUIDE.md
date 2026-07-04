# HR Performance Management System - User Guide

## Table of Contents
1. [Overview](#overview)
2. [Module Features](#module-features)
3. [Getting Started](#getting-started)
4. [User Roles & Permissions](#user-roles--permissions)
5. [Performance Cycle Management](#performance-cycle-management)
6. [Goal Setting & Tracking](#goal-setting--tracking)
7. [Evaluations](#evaluations)
8. [Performance Scoring](#performance-scoring)
9. [Appraisal Process](#appraisal-process)
10. [Performance Improvement Plans (PIP)](#performance-improvement-plans-pip)
11. [Appeals & Review](#appeals--review)
12. [Best Practices](#best-practices)
13. [FAQ](#faq)

---

## Overview

The **HR Performance Management System** is a comprehensive solution for managing employee performance evaluations through a structured 360-degree feedback approach. It facilitates the entire appraisal lifecycle from goal setting to final scorecard generation, with built-in support for performance improvement plans.

### Key Benefits
- **Structured Evaluation**: Multi-phase performance assessment process
- **360-Degree Feedback**: Evaluations from managers, peers, and subordinates
- **Goal Tracking**: SMART goal definition with progress monitoring
- **Automated Scoring**: Weighted calculations for fair assessments
- **Development Focus**: Performance improvement plans for low performers
- **Audit Trail**: Complete record of all evaluation activities

---

## Module Features

### 1. **Performance Cycles**
Master records that organize evaluations by period (Annual, Quarterly, etc.)
- Create and manage performance cycles
- Define important dates (goal submission, review dates, etc.)
- Track cycle status (Draft → Open → In Progress → Evaluation → Closed)
- View cycle statistics and progress

### 2. **Evaluator Assignment**
Define who will evaluate each employee
- Assign line managers, HODs, peers, and customers as evaluators
- Multi-level approval workflow
- Employee-specific evaluator mapping

### 3. **Performance Goals**
SMART goal definition with progress tracking
- Set objectives with measurable KPIs
- Track goal achievement percentage
- Multi-stage approval workflow
- Progress update history with evidence

### 4. **Coaching Sessions**
Track manager-employee meetings and discussions
- Schedule regular coaching sessions
- Record session notes and action items
- Follow-up scheduling
- Maintain coaching history

### 5. **Technical Evaluations**
Manager assessment of job-related performance
- Goal achievement scoring (60%)
- Quality of work (15%)
- Productivity (10%)
- Innovation (15%)
- Weighted score calculation

### 6. **Behavioral Evaluations**
Peer/subordinate feedback on competencies
- 6 competency areas (Teamwork, Communication, Leadership, Integrity, Initiative, Problem-solving)
- 1-5 rating scale
- Anonymous feedback option
- Multiple evaluators per employee

### 7. **Final Scorecards**
Consolidated appraisal with employee acknowledgement
- Auto-calculated final score
- Performance rating (Exceeds Expectations, Meets Expectations, Needs Improvement, Below Expectations)
- Employee review and acceptance
- Automatic PIP trigger if score < 60%

### 8. **Performance Improvement Plans (PIP)**
Structured support for underperforming employees
- Auto-created for scores below 60%
- Improvement areas and objectives
- Success criteria and support provided
- Regular progress tracking
- Outcome assessment (Met, Partially Met, Not Met)

### 9. **Appeal Records**
Employee dispute resolution process
- Appeal submission with evidence
- HR review and decision
- Resolution tracking
- Escalation capability

---

## Getting Started

### Initial Setup (HR Administrator)

1. **Access the Module**
   - Go to: **HR → Performance Management**
   - You'll see 5 main sections in the left menu

2. **Create a Performance Cycle**
   - Click: **Cycles → Create**
   - Fill in cycle details:
     - Name: (e.g., "2024 Annual Appraisal")
     - Start Date & End Date
     - Goal Submission Deadline
     - Mid-Year Review Date
     - Final Evaluation Date
   - Save as Draft initially

3. **System Requirements**
   - Employees must be created in **HR → Employees**
   - Users must be assigned to employee records
   - User groups configured (**HR User** or **HR Manager**)

---

## User Roles & Permissions

### **HR User**
- **Read**: All performance records
- **Create/Edit**: Own goals, progress updates, evaluations, coaching sessions
- **Cannot**: Delete records, approve cycles

### **HR Manager** (Full Access)
- **Create/Edit/Delete**: All performance records
- **Approve**: Performance cycles, goals, evaluations
- **Manage**: Employee appraisals and scorecards
- **Action**: Launch cycles, start evaluations, close cycles

### **Access Restrictions**
- Employees see only their own records
- Managers see team member records
- HR managers see all records
- Record-level security applied automatically

---

## Performance Cycle Management

### Step 1: Create Performance Cycle

1. Go to **Cycles** section
2. Click **Create**
3. Enter:
   ```
   Name: Annual Performance Review 2024
   Start Date: 2024-01-01
   End Date: 2024-12-31
   Goal Submission Deadline: 2024-02-15
   Mid-Year Review Date: 2024-06-30
   Final Evaluation Date: 2024-11-30
   HR Coordinator: [Select]
   ```
4. Click **Save** (Status: Draft)

### Step 2: Launch Cycle

1. Open the saved cycle
2. Click **Launch Cycle** button
3. Status changes to **Open**
4. Notifications sent to HR Coordinator

### Step 3: Assign Evaluators

1. In the cycle, go to **Evaluator Assignments** tab
2. Click **Create**
3. For each employee, fill:
   - Employee: [Select]
   - Line Manager: [Required]
   - HOD: [Optional]
   - Peers: [Up to 3]
   - Subordinates: [Up to 2]
   - Internal Customer: [Optional]
   - External Customer: [Optional - text field]
4. Click **Submit Assignment**
5. Wait for HR approval

### Step 4: Approve & Start

1. Open assignment record
2. Click **Approve Assignment** (HR Manager only)
3. Goal-setting phase begins
4. Employees receive notification to create goals

### Step 5: Start Evaluation Phase

1. Once goal deadline passes, open cycle
2. Click **Start Evaluation**
3. System validates all goals are approved
4. Status changes to **Evaluation**
5. Evaluators can now submit evaluations

### Step 6: Close Cycle

1. After evaluation deadline
2. Click **Close Cycle**
3. Status changes to **Closed**
4. Archives cycle for historical records
5. Scorecards auto-generated and ready for review

### Viewing Cycle Progress

In any cycle, see:
- **Total Employees**: How many in this cycle
- **Goals Approved**: % of goals approved
- **Evaluations Pending**: Count remaining
- **Evaluations Completed**: Count finished

---

## Goal Setting & Tracking

### Creating Performance Goals

**Who Can Create**: Employees (during goal submission phase)

1. Go to **Goals** section
2. Click **Create**
3. Fill in SMART goal details:
   ```
   Cycle: [Select]
   Goal Code: (Auto-generated - GOAL-001)
   Goal Description: Clear description of the goal
   Objective: What needs to be achieved
   KPI: Measurable indicator
   Measurement Criteria: How success is measured
   Weight: % of overall performance (e.g., 20%)
   Start Date: Beginning of performance period
   End Date: End date for goal achievement
   Expected Outcome: Desired result
   Required Tools: Resources needed
   Required Training: Skills to develop
   Resources Needed: Budget, people, etc.
   ```
4. Click **Save** (Status: Draft)

### Goal Workflow

**Employee Creates → Manager Reviews → Employee Comments → Manager Approves → Manager Locks**

#### Stage 1: Manager Review
- Manager clicks **Request Employee Review**
- Status: Manager Review
- Goal locked from employee edits

#### Stage 2: Employee Response
- Employee reviews goal
- Option A: **Agree Goal** → Status: Employee Agreed
- Option B: **Request Modification** → Manager edits

#### Stage 3: Manager Approval
- If employee agreed: Manager clicks **Approve Goal**
- Status: Approved
- Weight locked

#### Stage 4: Locked State
- Manager clicks **Lock Goal**
- Status: Locked
- No further edits allowed

#### Final: Close Goal
- At end of cycle: Click **Close Goal**
- Enter **Actual Achievement Percentage** (0-100%)
- Status: Closed

### Tracking Progress

1. Open goal record
2. Go to **Progress Updates** tab
3. Click **Create Progress Update**
4. Enter:
   - Date Updated: Today
   - Progress Percentage: Current % towards goal
   - Achievements: What has been accomplished
   - Challenges: Obstacles faced
   - Support Required: Help needed
   - Evidence Attachments: Documents, screenshots, etc.
5. Save

View visual progress bar on goal form showing % completion.

### Example: Quarterly Sales Goal
```
Goal: Increase customer base by 25%
Objective: Add 50 new customers
KPI: Customer acquisition count
Measurement Criteria: New contracts signed
Weight: 25%
Start: 2024-01-01
End: 2024-03-31
Expected Outcome: 50 new customers, $2M revenue
```

---

## Evaluations

### Two Types of Evaluations

#### 1. Technical Evaluations (Manager/HOD)
**Purpose**: Assess job performance against goals and competencies

**Scoring Breakdown**:
- Goal Achievement Score: 60% weight
- Quality of Work Score: 15% weight
- Productivity Score: 10% weight
- Innovation Score: 15% weight
- **Final Technical Score**: Weighted average (0-100)

**How to Complete**:
1. Go to **Evaluations → Technical Evaluations**
2. Click **Create**
3. Select:
   - Cycle: [Select]
   - Goal: [Employee's goal]
   - Evaluator: [Your name - auto-filled]
4. Rate each competency (0-100):
   - Goal Achievement Score: Based on actual achievement %
   - Quality of Work Score: Quality vs standard
   - Productivity Score: Output efficiency
   - Innovation Score: Improvements suggested
5. Add Comments: Specific feedback and observations
6. Click **Submit Evaluation**
7. Status: Submitted (locked from further edits)

**Example Scores**:
- Goal Achievement: 85 (achieved 85% of goal)
- Quality of Work: 90 (excellent quality)
- Productivity: 80 (good output)
- Innovation: 75 (some improvements)
- **Final Technical Score**: (85×0.60) + (90×0.15) + (80×0.10) + (75×0.15) = **83.0**

#### 2. Behavioral Evaluations (Peers/Subordinates/Customers)
**Purpose**: Assess soft skills and competencies

**6 Competency Areas** (1-5 rating scale):
1. **Teamwork**: Collaboration and team contribution
2. **Communication**: Clarity and listening skills
3. **Leadership**: Ability to guide and motivate
4. **Integrity**: Honesty and reliability
5. **Initiative**: Proactiveness and ownership
6. **Problem-solving**: Analytical and creative thinking

**How to Complete**:
1. Go to **Evaluations → Behavioral Evaluations**
2. Click **Create**
3. Select:
   - Cycle: [Select]
   - Goal: [Employee's goal]
   - Evaluator: [Your name]
   - Evaluator Type: Peer / Subordinate / Internal Customer / External Customer
4. Rate each competency (1-5 scale):
   - 1 = Below Expectations
   - 2 = Needs Improvement
   - 3 = Meets Expectations
   - 4 = Exceeds Expectations
   - 5 = Outstanding
5. Optional: Check **Anonymous Feedback** checkbox
6. Add feedback and comments
7. Click **Submit Evaluation**

**Example Behavioral Scores**:
- Teamwork: 4 (Exceeds)
- Communication: 4 (Exceeds)
- Leadership: 3 (Meets)
- Integrity: 5 (Outstanding)
- Initiative: 4 (Exceeds)
- Problem-solving: 4 (Exceeds)
- **Behavioral Average**: 4.1/5

### Coaching Sessions

**Purpose**: Document manager-employee discussions and development

1. Go to **Coaching Sessions**
2. Click **Create**
3. Fill in:
   - Cycle: [Select]
   - Employee: [Select]
   - Supervisor: [Your name]
   - Meeting Date: When meeting occurred
   - Meeting Duration: (hours)
   - Objectives Discussed: Topics covered
   - Employee Feedback: Employee's input
   - Supervisor Feedback: Your observations
   - Action Items: Agreed-upon next steps
   - Follow-up Date: When to meet again
4. Click **Save** (Status: Scheduled)
5. After meeting: Click **Mark Completed**

---

## Performance Scoring

### Automatic Score Calculation

The system **automatically calculates** the final score from three components:

#### Component 1: Goal Achievement (30% of final score)
- **Source**: Goal achievement % from closed goals
- **Calculation**: Average of all actual_achievement_percentage fields
- **Weight**: 30% of final score

#### Component 2: Technical Metrics (40% of final score)
- **Source**: Technical evaluations from manager(s)
- **Calculation**: Average of all technical_score values
- **Weight**: 40% of final score

#### Component 3: Behavioral Metrics (30% of final score)
- **Source**: Behavioral evaluations from peers/subordinates/customers
- **Calculation**: Average of all behavioral_average_score values
- **Weight**: 30% of final score

#### Final Score Formula
```
Final Score = (Goal Achievement × 0.30) + (Technical Average × 0.40) + (Behavioral Average × 0.30)
Result: 0-100 scale
```

#### Performance Rating
```
90-100 → Exceeds Expectations (Outstanding performer)
75-89  → Meets Expectations (Solid performer)
60-74  → Needs Improvement (Development required)
0-59   → Below Expectations (Performance improvement required)
```

### Example Calculation

**Employee: John Smith**

**Goals** (3 total):
- Goal 1: Actual Achievement = 95%
- Goal 2: Actual Achievement = 80%
- Goal 3: Actual Achievement = 90%
- **Goal Achievement Average = 88.3%**

**Technical Evaluations** (2 total):
- Manager 1: Technical Score = 82
- Manager 2 (HOD): Technical Score = 88
- **Technical Average = 85**

**Behavioral Evaluations** (4 total):
- Peer 1: Behavioral Score = 4.0/5 = 80%
- Peer 2: Behavioral Score = 4.2/5 = 84%
- Subordinate 1: Behavioral Score = 3.8/5 = 76%
- Customer: Behavioral Score = 4.1/5 = 82%
- **Behavioral Average = 80.5%**

**FINAL SCORE CALCULATION**:
```
(88.3 × 0.30) + (85 × 0.40) + (80.5 × 0.30)
= 26.49 + 34 + 24.15
= 84.64 → Rounds to 85/100
```

**Performance Rating**: **Meets Expectations** (75-89 range)

---

## Appraisal Process

### Step 1: Employee Review Scorecard

1. HR or Manager opens **Final Scorecard**
2. Click **Request Employee Review**
3. Employee receives notification
4. Status: Pending Employee Review

### Step 2: Employee Acknowledgement

1. Employee opens scorecard
2. Reads final score breakdown:
   - Average Goal Achievement
   - Average Technical Score
   - Average Behavioral Score
   - Overall Final Score
   - Performance Rating
3. Option A: **Accept Scorecard**
   - Click button
   - Status: Accepted
   - If score < 60%, PIP auto-creates
4. Option B: **Appeal Scorecard**
   - Click **Appeal**
   - Creates Appeal Record
   - Status: Appealed

### Step 3: HR Approval

1. HR Manager opens scorecard
2. Reviews employee comments
3. Checks PIP creation (if applicable)
4. Click **Approve Scorecard**
5. Status: Approved
6. Appraisal complete

### View Scorecard Components

Scorecard shows:
- **Employee Info**: Name, department, manager
- **Goal Achievement**: Average % of goals met
- **Technical Metrics**: Average manager rating
- **Behavioral Metrics**: Average peer/customer rating
- **Final Score**: Overall rating (0-100)
- **Performance Rating**: Text rating (Exceeds/Meets/Needs/Below)
- **Employee Comments**: Any feedback from employee
- **PIP Status**: "Requires PIP" if score < 60%

---

## Performance Improvement Plans (PIP)

### Automatic PIP Creation

**When**: Employee final score < 60% (Below Expectations)
**Who**: Auto-created when employee accepts scorecard or HR approves
**Status**: Active - requires action

### PIP Components

A PIP includes:
1. **Improvement Areas**: Specific areas needing improvement
2. **Objectives**: Clear goals for improvement
3. **Success Criteria**: How improvement is measured
4. **Support Provided**: Training, coaching, resources
5. **Review Frequency**: How often to check progress (Weekly, Bi-weekly, Monthly)
6. **Duration**: Typically 13 weeks (3 months)
7. **Progress Tracking**: Regular updates on improvement

### PIP Workflow

#### Phase 1: Activation
1. Manager opens PIP record
2. Click **Activate PIP**
3. Employee and manager notified
4. Status: Active
5. Progress tracking begins

#### Phase 2: Regular Review
1. At each review frequency:
   - Manager meets with employee
   - Discuss progress on objectives
   - Identify support needed
   - Record session notes

2. Click **Update Progress**
3. Fill in:
   - Progress Description: What's been done
   - Achievements: Wins so far
   - Challenges: Obstacles
   - Support Provided: What was given
   - Next Steps: What's coming

#### Phase 3: Completion

At end of PIP duration:
1. Manager clicks **Complete PIP**
2. Select outcome:
   - **Met**: Employee improved to acceptable level
   - **Partially Met**: Some improvement but not sufficient
   - **Not Met**: No improvement, performance issue continues

3. Follow-up action options:
   - **Continue Employment**: Employee back to normal (if Met)
   - **Extension**: Continue PIP for another period
   - **Disciplinary**: Escalate to formal discipline
   - **Termination**: Initiate separation process

### PIP Example

**Employee**: Sarah Johnson  
**Performance Issue**: Technical skills and productivity below standard
**Score**: 55% (Below Expectations)

**PIP Details**:
```
Improvement Areas:
- Technical competency in system configuration
- Task completion speed
- Quality of deliverables

Objectives:
1. Complete advanced training certification
2. Reduce avg task completion time from 8 to 5 days
3. Achieve 95%+ quality in deliverables

Success Criteria:
- Certification completed by Week 6
- Average time < 5 days by Week 10
- Zero defects in final 2 weeks

Support Provided:
- Online training course access
- Weekly 1-on-1 coaching
- Assigned mentor/buddy
- Extra resources allocation

Duration: 13 weeks
Review Frequency: Weekly
```

**Progress Update (Week 4)**:
- Completed 60% of training
- Task time improved to 6.5 days (from 8)
- Quality improved but still some issues
- **Status**: On track but needs more support

**Completion (Week 13)**:
- All training completed ✓
- Task time: 4.8 days ✓
- Quality: 98% ✓
- **Outcome**: Met
- **Action**: Continue employment, back to normal review cycle

---

## Appeals & Review

### When to Appeal

Employee can appeal if they disagree with:
- Final score calculation
- Evaluation fairness
- Bias in assessment
- Scoring methodology

### How to Appeal

1. Employee opens **Final Scorecard**
2. Clicks **Appeal Scorecard**
3. **Appeal Record** created automatically
4. Fill in:
   - Appeal Reason: Why appealing (required)
   - Supporting Evidence: Documents, examples
   - Evidence Attachments: Files/links
5. Status: Submitted

### HR Review Process

1. HR Manager receives notification
2. Opens Appeal Record
3. Reviews:
   - Appeal reason and evidence
   - Original evaluation scores
   - Evaluation comments
   - Supporting documentation
4. Conducts investigation if needed:
   - May interview evaluators
   - May review evaluation process
   - May request additional assessment
5. Click **Mark Resolved**
6. Select resolution:
   - **Sustained**: Appeal upheld, score adjusted
   - **Dismissed**: Appeal rejected, original score stands
   - **Partial**: Partial adjustment made
7. Enter:
   - Review Notes: Why decision made
   - Adjusted Final Score: If applicable
8. Status: Resolved

### Appeal Outcomes

**If Sustained**:
- Final score adjusted to higher value
- Employee notified of outcome
- May prevent PIP creation if new score > 60%

**If Dismissed**:
- Original score upheld
- Employee notified of decision
- PIP remains if applicable

**If Partial**:
- Score partially adjusted
- Transparent about changes
- Clear communication of decision

---

## Best Practices

### For Managers

1. **Set Clear Goals**
   - Use SMART framework (Specific, Measurable, Achievable, Relevant, Time-bound)
   - Align with business objectives
   - Ensure employee understands expectations

2. **Regular Feedback**
   - Don't wait for appraisal to discuss performance
   - Monthly or quarterly coaching sessions
   - Address issues promptly
   - Celebrate achievements

3. **Objective Evaluation**
   - Base scores on evidence and observations
   - Avoid personal bias
   - Compare fairly within team
   - Document comments with examples

4. **Support Improvement**
   - Provide training and resources
   - Assign mentors for development
   - Regular check-ins during PIP
   - Clear expectations about improvement

5. **Complete Assessments**
   - Submit evaluations on time
   - Provide detailed comments
   - Include specific examples
   - Finalize before deadline

### For Employees

1. **Own Your Goals**
   - Create realistic but challenging goals
   - Track progress regularly
   - Update regularly with evidence
   - Request help when struggling

2. **Gather Evidence**
   - Keep records of achievements
   - Collect feedback from peers
   - Document completed projects
   - Save performance metrics

3. **Continuous Updates**
   - Don't wait for appraisal
   - Share progress with manager
   - Discuss challenges early
   - Request feedback frequently

4. **Professional Development**
   - Identify skill gaps
   - Take relevant training
   - Seek mentoring opportunities
   - Document improvements

5. **Engage in Process**
   - Provide honest self-assessment
   - Accept constructive feedback
   - Ask questions about scores
   - Discuss development plan

### For HR Teams

1. **Process Management**
   - Create cycles well in advance
   - Set realistic deadlines
   - Communicate dates clearly
   - Track completion status

2. **Quality Assurance**
   - Review all evaluations for consistency
   - Ensure proper weighting
   - Check for biases
   - Validate calculations

3. **Timeline Adherence**
   - Start cycles on schedule
   - Follow established phases
   - Close cycles promptly
   - Maintain audit trail

4. **Communication**
   - Regular updates to all parties
   - Clear instructions
   - Timely notifications
   - Feedback to management

5. **Data Security**
   - Restrict access appropriately
   - Maintain confidentiality
   - Archive completed cycles
   - Backup critical data

---

## FAQ

### General Questions

**Q1: How often should we run performance cycles?**  
A: Typically annually, but organizations can run quarterly or semi-annual cycles. Most companies use annual with mid-year check-ins.

**Q2: Can an employee be their own evaluator?**  
A: No. The system prevents self-evaluation. Minimum requirement is manager evaluation.

**Q3: What happens if a goal deadline is missed?**  
A: The system allows extensions. Manager can edit goal dates if circumstances change, but must update before approval.

**Q4: Can evaluators see other evaluators' feedback?**  
A: No. Evaluations are confidential between evaluator and HR. Employees see final consolidated score only.

---

### Goal-Related Questions

**Q5: Can an employee change goals after approval?**  
A: No. Once manager approves and locks the goal, it cannot be edited. This prevents goal-moving.

**Q6: What if an employee leaves mid-cycle?**  
A: Manager must close all goals. Evaluations are conducted up to departure date. Scorecard reflects partial-period performance.

**Q7: How is goal achievement percentage calculated?**  
A: Manager and employee discuss at end of period, based on:
- Measurement criteria achievement
- External factors and obstacles
- Quality vs. quantity
- Evidence and documentation

**Q8: Can weights be changed during the cycle?**  
A: No. Goal weights are locked after approval to ensure fairness.

---

### Evaluation Questions

**Q9: What's the difference between technical and behavioral evaluations?**  
A: 
- **Technical**: Job-specific performance (goals, quality, productivity)
- **Behavioral**: Soft skills (teamwork, communication, leadership)

**Q10: Who should provide behavioral evaluations?**  
A: Peers (colleagues), subordinates (direct reports), and customers. 360-degree perspective.

**Q11: Can evaluations be anonymous?**  
A: Yes. Behavioral evaluations have an optional "Anonymous Feedback" checkbox.

**Q12: What if an evaluator doesn't submit their evaluation?**  
A: System shows pending evaluations in cycle dashboard. HR can send reminders or reassign to another evaluator.

---

### Scoring Questions

**Q13: How is the final score calculated?**  
A: Weighted average of three components:
- Goals: 30%
- Technical: 40%
- Behavioral: 30%

**Q14: Can managers override the calculated score?**  
A: No. The system calculates automatically to prevent bias. But manager can provide context in comments.

**Q15: What if only one evaluator provided feedback?**  
A: Score is still calculated based on available data. Ideally, multiple evaluators provide perspective.

**Q16: How are ratings determined from scores?**  
A:
- 90-100: Exceeds Expectations
- 75-89: Meets Expectations
- 60-74: Needs Improvement
- 0-59: Below Expectations

---

### Appeal Questions

**Q17: How long can an employee appeal after scorecard?**  
A: Typically 30 days. Check with HR for your organization's policy.

**Q18: Can an appeal change the rating?**  
A: Yes. If appeal is sustained, the score is adjusted, which may change the rating.

**Q19: What happens during appeal investigation?**  
A: HR may:
- Interview evaluators
- Review evaluation process
- Request additional assessment
- Check for procedural errors

**Q20: Can employee see evaluation comments during appeal?**  
A: Yes. HR provides copies of relevant evaluations to support appeal review.

---

### PIP Questions

**Q21: Is PIP mandatory if score < 60%?**  
A: Yes. The system auto-creates PIP when employee accepts scorecard below 60%.

**Q22: How long should a PIP last?**  
A: Standard duration is 13 weeks (3 months), but can be adjusted based on role and issues.

**Q23: Can employee refuse PIP?**  
A: No. PIP is mandatory for Below Expectations performers. Refusal may escalate to discipline.

**Q24: What happens if PIP not met?**  
A: Options include:
- Extension for another period
- Escalation to formal discipline
- Performance-based termination

**Q25: Can an employee succeed in PIP?**  
A: Yes, absolutely. With support and commitment, many employees improve and return to normal evaluation.

---

### Access & Permissions Questions

**Q26: What can HR Users see?**  
A: All performance records in read-only mode, plus can create/edit own records.

**Q27: What can HR Managers do?**  
A: Full access - create, edit, delete, approve, and manage all performance records.

**Q28: How are record permissions enforced?**  
A: Automatically through:
- HR Groups (User vs. Manager)
- Employee relationships (see own + team)
- Manager hierarchy (see direct reports)

**Q29: Can an HR User approve a cycle?**  
A: No. Only HR Managers can approve cycles and assignments.

**Q30: What if manager leaves company?**  
A: HR must reassign all evaluations to new manager. Existing evaluations attributed to departing manager remain in system.

---

### Troubleshooting

**Q31: Why can't I create a goal?**  
A: 
- Cycle must be in "Open" status (not Draft)
- Goal submission deadline may have passed
- You may not have permission (check user group)

**Q32: Why is final score not calculated?**  
A: Waiting for required evaluations:
- Need at least one technical evaluation
- Need at least one behavioral evaluation
- All goals must be closed

**Q33: Why can't I edit my evaluation?**  
A: You already submitted it. To edit, contact HR to unlock.

**Q34: Where are my coaching session reminders?**  
A: Coaching sessions don't auto-remind. Manager must create and schedule. Check calendar for upcoming sessions.

**Q35: Can I export performance data?**  
A: Contact HR/Admin. System typically exports to Excel/PDF by cycle.

---

## Getting Help

**Questions or Issues?**
- Contact your HR Department
- Check with your Manager
- Contact HR Coordinator listed in cycle
- Consult with IT for system access issues

**Document Retention**
- All cycles archived after closure
- Performance history maintained 7+ years
- Access historical cycles under: **Cycles → [Cycle Name]**

---

## Key Contacts

| Role | Contact |
|------|---------|
| HR Coordinator | [Listed in Cycle] |
| HR Manager | [Department HR] |
| System Admin | [IT Department] |
| HR Director | [HR Department] |

---

**Last Updated**: 2026  
**Version**: 1.0  
**For**: Taghini Farm HR Performance Management System
