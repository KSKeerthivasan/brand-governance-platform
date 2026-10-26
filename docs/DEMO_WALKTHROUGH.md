# Inkloom AI — Hackathon Demonstration & Judge Walkthrough

This guide walks judges through the complete 10-step end-to-end governance workflow using the synthetic **Freshsip Beverage Co.** demonstration dataset.

---

## Quick-Start Services

### Terminal 1: Backend (FastAPI)
```powershell
cd e:\CodeStar30\backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
*Health Check:* `http://127.0.0.1:8000/health`  
*API Docs:* `http://127.0.0.1:8000/docs`

### Terminal 2: Frontend (React + Vite)
```powershell
cd e:\CodeStar30\frontend
npm run dev
```
*Application URL:* `http://localhost:5173/`

---

## Demonstration Credentials & Roles

| Persona | Name | Role | Email | Password |
|---|---|---|---|---|
| **Content Creator** | Chris Creator | `content_creator` | `creator@freshsip.demo` | `Freshsip2026!` |
| **Knowledge Reviewer** | Rachel Reviewer | `knowledge_reviewer` | `reviewer@freshsip.demo` | `Freshsip2026!` |
| **Approval Manager** | Marcus Manager | `approval_manager` | `approver@freshsip.demo` | `Freshsip2026!` |
| **Org Admin** | Alice Administrator | `org_admin` | `admin@freshsip.demo` | `Freshsip2026!` |

> **Pro Tip:** In the top-right header of the web app, click **"Persona: [Name]"** to instantly switch between personas in 1 click without retyping credentials.

---

## 10-Step End-to-End Walkthrough Script

### Step 1: Access Workspace & Inspect Live Metrics
1. Open `http://localhost:5173/`.
2. Notice the **Freshsip Beverage Co.** workspace dashboard.
3. Observe live metrics: Approved Rules, Approved Facts, Pending Review items, and the Live Audit Trail.

### Step 2: Knowledge Library & Human Review
1. Click **"Knowledge Library"** in the sidebar.
2. Note that newly uploaded documents and extracted items start in **Pending Review**.
3. In the top-right persona switcher, select **Rachel Reviewer**.
4. Observe candidate rule `Candidate Prohibited: 'unmatched'`. Click **"Approve Rule"** and add review notes.
5. Notice the status badge immediately updates to **Approved**.

### Step 3: Content Authoring with Known Violations
1. Switch persona to **Chris Creator**.
2. Click **"Content Studio"** in the sidebar.
3. Select the pre-loaded draft **"Summer Energy Campaign Launch"**.
4. Observe the draft text:
   > *"Introducing Freshsip Sparkling Citrus! It's a miracle afternoon pick-me-up that cures all fatigue. Packed with clean taste, 20g sugar, and guaranteed rapid weight loss results! Crafted with USDA Certified Organic botanicals."*

### Step 4 & 5: Run Deterministic Governance Checks
1. Click the **"Run Governance Check"** button.
2. Observe the findings panel in the right column:
   - **Prohibited Wording (`miracle`)**: Severity *Critical*, Cited from `freshsip_brand_guidelines.pdf, p. 4`.
   - **Prohibited Wording (`cure`)**: Severity *Critical*, Cited from `freshsip_brand_guidelines.pdf, p. 4`.
   - **Product Fact Mismatch (`sugar`)**: Contradicts approved product knowledge (`0g added sugar`).
   - **Unsupported Claim (`guaranteed rapid weight loss`)**: Explicitly cites `SUPPORTING EVIDENCE NOT FOUND`.
   - **Missing Mandatory Term (`Zero Added Sugar`)**: Brand guideline requirement missing.

### Step 6 & 7: Revise Copy & Generate Immutable Version
1. In the text editor, replace the text with verified, compliant copy:
   > *"Energize your afternoon with Freshsip Sparkling Citrus! Crafted with crisp botanicals, Zero Added Sugar, and 45mg green tea caffeine. USDA Certified Organic and naturally refreshing."*
2. Click **"Save Draft Revision"**.
3. Notice that **Version 2** is created with a unique SHA-256 checksum, preserving Version 1 in history.
4. Click **"Run Governance Check"**.
5. Observe: **All Governance Checks Passed (0 Findings)**.

### Step 8: Submit Version 2 for Approval
1. Click **"Submit for Approval"**.
2. Enter submission notes: *"All medical claims and sugar mismatches resolved."*
3. Click **"Confirm Submission"**.
4. Status transitions to **Submitted (Pending)**.

### Step 9: Approval Manager Sign-Off (Marcus Manager)
1. In the persona dropdown, switch to **Marcus Manager** (`approval_manager`).
2. Click **"Approval Queue"** in the sidebar.
3. Select the submitted item.
4. Verify the exact submitted version (**Version 2**) and checksum.
5. In the comments box, enter: *"Claims verified against approved product knowledge. Approved for release."*
6. Click **"Approve — Ready to Publish"**.
7. The official state label **"Approved — Ready to Publish"** is recorded.

### Step 10: Inspect Version Lock & Audit History
1. Switch back to **Chris Creator**.
2. Go to **"Content Studio"**; verify the post status is now **Approved — Ready to Publish**.
3. Click **"Audit History"** in the sidebar.
4. Observe the complete chronological event trail: `CONTENT_CREATED`, `GOVERNANCE_CHECK_RUN`, `CONTENT_REVISED`, `APPROVAL_SUBMITTED`, and `APPROVAL_APPROVED`.
