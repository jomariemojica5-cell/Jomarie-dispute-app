import streamlit as st
import pdfplumber
import re
from bs4 import BeautifulSoup

st.set_page_config(page_title="Opsify Dispute Automation Tool", page_icon="🛡️", layout="wide")

st.title("🛡️ Opsify Dispute Automation Tool (3B PDF & HTML Supported)")
st.write("Upload 3-Bureau Credit Report (PDF, HTML, or TXT) to accurately parse Negative Items, Late Payments, Unattached Inquiries, and Personal Info.")

# -------------------------------------------------------------
# SIDEBAR - CLIENT DETAILS
# -------------------------------------------------------------
st.sidebar.header("👤 Client Details")
client_name = st.sidebar.text_input("Client Full Name", "Sophia Baker")
client_dob = st.sidebar.text_input("Date of Birth", "09/07/1974")
client_ssn = st.sidebar.text_input("SSN (Last 4)", "9139")
client_address = st.sidebar.text_area("Current Address", "1119 Madison St, Bogalusa Louisiana 70427")
bureau = st.sidebar.selectbox("Select Target Bureau", ["Experian", "Equifax", "TransUnion"])

uploaded_file = st.file_uploader("Upload Credit Report (PDF, HTML, or TXT)", type=["pdf", "html", "htm", "txt"])

if uploaded_file is not None:
    file_type = uploaded_file.name.split(".")[-1].lower()
    
    incorrect_addresses = []
    negative_accounts = []
    positive_creditors = []
    unattached_inquiries = []
    
    raw_text = ""

    # -------------------------------------------------------------
    # ADVANCED PDF 3B PARSER ENGINE
    # -------------------------------------------------------------
    if file_type == "pdf":
        with st.spinner("Extracting multi-page 3-Bureau PDF report structure..."):
            with pdfplumber.open(uploaded_file) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    # Layout extraction to preserve column formats
                    text = page.extract_text(layout=True)
                    if text:
                        raw_text += text + "\n"
        
        lines = [line for line in raw_text.split("\n") if line.strip()]
        
        # Keywords for status checks
        derog_keywords = ["CHARGE-OFF", "CHARGED OFF", "COLLECTION", "REPOSSESSION", "FORECLOSURE", "DEROGATORY", "PAST DUE", "PLACED FOR COLLECTION"]
        late_keywords = ["LATE 30", "LATE 60", "LATE 90", "30 DAYS", "60 DAYS", "90 DAYS", "120 DAYS", "LATE"]
        
        current_section = None
        
        for idx, line in enumerate(lines):
            line_upper = line.upper()
            
            # --- SECTION DETECTORS ---
            if "PERSONAL INFORMATION" in line_upper or "ADDRESS HISTORY" in line_upper:
                current_section = "PERSONAL"
            elif "ACCOUNT HISTORY" in line_upper or "TRADELINES" in line_upper or "CREDIT ACCOUNTS" in line_upper:
                current_section = "ACCOUNTS"
            elif "INQUIRIES" in line_upper or "HARD INQUIRIES" in line_upper:
                current_section = "INQUIRIES"

            # 1. PARSE ADDRESSES
            if current_section == "PERSONAL" or "ADDRESS" in line_upper:
                # Look for street address patterns
                addr_match = re.search(r'\d+\s+[A-Za-z0-9\s,\.]+(?:ST|AVE|RD|DR|BLVD|LN|CT|WAY|SUITE|APT|BOX)', line_upper)
                if addr_match:
                    found_addr = addr_match.group(0).strip()
                    # If not matching current client address
                    if client_address.strip().lower() not in found_addr.lower() and len(found_addr) > 10:
                        if found_addr not in incorrect_addresses:
                            incorrect_addresses.append(found_addr)

            # 2. PARSE ACCOUNTS (Negative vs Positive Tradelines)
            if any(kw in line_upper for kw in derog_keywords + late_keywords):
                # Try to capture creditor name (usually 1 to 3 lines above or same line)
                creditor = "UNKNOWN CREDITOR"
                for offset in [1, 2, 3]:
                    if idx - offset >= 0:
                        prev_line = lines[idx - offset].strip()
                        if len(prev_line) > 2 and not any(k in prev_line.upper() for k in derog_keywords):
                            creditor = prev_line[:35]
                            break
                
                # Extract Account Number
                acct_num = "N/A"
                acct_match = re.search(r'#?\s*([A-Z0-9\*]{4,16})', line)
                if acct_match:
                    acct_num = acct_match.group(1)
                
                # Determine Exact Reason/Status
                reason = "Derogatory / Late Status"
                if any(kw in line_upper for kw in ["CHARGE-OFF", "CHARGED OFF"]):
                    reason = "Charged Off Account"
                elif "COLLECTION" in line_upper:
                    reason = "Collection Account"
                elif any(kw in line_upper for kw in late_keywords):
                    reason = "Late Payment History Recorded"
                elif "PAST DUE" in line_upper:
                    reason = "Past Due Balance"

                # Check duplication
                if not any(acc['creditor'] == creditor and acc['acct'] == acct_num for acc in negative_accounts):
                    negative_accounts.append({
                        "creditor": creditor,
                        "acct": acct_num,
                        "reason": reason,
                        "raw_status": line_upper[:45]
                    })
            
            # Record Positive / Open Creditors to filter inquiries
            if any(p_kw in line_upper for p_kw in ["OPEN/NEVER LATE", "PAYS AS AGREED", "OK", "CURRENT"]):
                for offset in [1, 2, 3]:
                    if idx - offset >= 0:
                        pos_cred = lines[idx - offset].strip().upper()
                        if len(pos_cred) > 3:
                            positive_creditors.append(pos_cred[:20])

            # 3. PARSE HARD INQUIRIES
            if current_section == "INQUIRIES" or "INQUIRY" in line_upper:
                # Detect date format MM/DD/YYYY or Mon DD, YYYY
                date_match = re.search(r'(\d{2}/\d{2}/\d{4}|\b(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+\d{1,2},\s+20\d{2}\b)', line_upper)
                if date_match:
                    inq_date = date_match.group(0)
                    inq_creditor = re.sub(r'(\d{2}/\d{2}/\d{4}|\b(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+\d{1,2},\s+20\d{2}\b)', '', line_upper).strip()
                    
                    if len(inq_creditor) > 3 and not any(h in inq_creditor for h in ["PERMISSIBLE", "FILE", "SHARED", "TOTAL"]):
                        # Check if connected to an open positive creditor account
                        is_connected = any(pos_c in inq_creditor or inq_creditor in pos_c for pos_c in positive_creditors if len(pos_c) > 3)
                        
                        if not is_connected:
                            if not any(inq['creditor'] == inq_creditor[:30] for inq in unattached_inquiries):
                                unattached_inquiries.append({
                                    "creditor": inq_creditor[:30],
                                    "date": inq_date
                                })

    # -------------------------------------------------------------
    # HTML PARSER FALLBACK
    # -------------------------------------------------------------
    elif file_type in ["html", "htm"]:
        content = uploaded_file.read().decode("utf-8", errors="ignore")
        soup = BeautifulSoup(content, "html.parser")
        
        account_blocks = soup.find_all(class_=re.compile(r'account-row|tradeline', re.I))
        for block in account_blocks:
            creditor = block.find(class_=re.compile(r'creditor-name|account-name', re.I))
            status = block.find(class_=re.compile(r'account-status|status', re.I))
            acct_num = block.find(class_=re.compile(r'account-number|acct-num', re.I))
            
            c_name = creditor.get_text(strip=True) if creditor else "UNKNOWN CREDITOR"
            s_val = status.get_text(strip=True).upper() if status else ""
            a_num = acct_num.get_text(strip=True) if acct_num else "N/A"
            
            if any(k in s_val for k in ["COLLECTION", "CHARGE-OFF", "PAST DUE", "DELINQUENT", "LATE"]):
                negative_accounts.append({"creditor": c_name, "acct": a_num, "reason": "Derogatory/Late Status", "raw_status": s_val})

    st.success("PDF/HTML Analysis Complete!")

    # -------------------------------------------------------------
    # DASHBOARD DISPLAY
    # -------------------------------------------------------------
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("📍 Incorrect Personal Info")
        if incorrect_addresses:
            for addr in incorrect_addresses:
                st.warning(f"Delete Address: {addr}")
        else:
            st.info("No extra/incorrect addresses detected.")

    with col2:
        st.subheader("🚨 Negative & Late Accounts")
        if negative_accounts:
            for acc in negative_accounts:
                st.error(f"**{acc['creditor']}**\n- Acct #: `{acc['acct']}`\n- Type: **{acc['reason']}**\n- Detail: {acc['raw_status']}")
        else:
            st.info("No derogatory or late accounts flagged.")

    with col3:
        st.subheader("🔎 Unattached Inquiries")
        if unattached_inquiries:
            for inq in unattached_inquiries:
                st.error(f"**{inq['creditor']}**\nDate: {inq['date']}\n*(Not linked to any open tradeline)*")
        else:
            st.info("No unattached hard inquiries flagged.")

    st.markdown("---")

    # -------------------------------------------------------------
    # AUTOMATED DISPUTE LETTER GENERATOR
    # -------------------------------------------------------------
    st.subheader("📄 Generated Metro 2 / FCRA Dispute Letter")
    
    letter_text = f"FROM:\n{client_name}\n{client_address}\nDOB: {client_dob} | SSN (Last 4): {client_ssn}\n\n"
    letter_text += f"TO:\n{bureau} Dispute Department\n\n"
    letter_text += "SUBJECT: FORMAL DEMAND FOR INVESTIGATION & REMOVAL OF INACCURATE DATA (FCRA § 611 & § 604)\n\n"
    letter_text += "To Whom It May Concern,\n\n"
    letter_text += "I am writing to formally dispute the following inaccurate, unverified, and unauthorized items appearing on my credit file.\n\n"

    if incorrect_addresses:
        letter_text += "1. INACCURATE PERSONAL INFORMATION (FCRA § 605):\n"
        for addr in incorrect_addresses:
            letter_text += f"   - PLEASE DELETE INACCURATE ADDRESS: {addr}\n"
        letter_text += "\n"

    if negative_accounts:
        letter_text += "2. DEROGATORY & UNVERIFIED ACCOUNTS (FCRA § 611):\n"
        for acc in negative_accounts:
            letter_text += f"   - Creditor: {acc['creditor']} | Account #: {acc['acct']} | Dispute Reason: {acc['reason']} ({acc['raw_status']})\n"
        letter_text += "\n"

    if unattached_inquiries:
        letter_text += "3. UNAUTHORIZED HARD INQUIRIES (FCRA § 604 - NO PERMISSIBLE PURPOSE):\n"
        for inq in unattached_inquiries:
            letter_text += f"   - Inquiry Creditor: {inq['creditor']} | Date: {inq['date']} (No open account exists with this creditor)\n"
        letter_text += "\n"

    letter_text += "Please complete your reinvestigation within thirty (30) days as required under federal law and send an updated copy of my credit report.\n\n"
    letter_text += f"Sincerely,\n{client_name}"

    st.text_area("Review Letter Draft", letter_text, height=350)
    
    st.download_button(
        label="📥 Download Dispute Letter (.TXT)",
        data=letter_text,
        file_name=f"{client_name.replace(' ', '_')}_{bureau}_Dispute_Letter.txt",
        mime="text/plain"
    )
