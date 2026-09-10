import streamlit as st
import pdfplumber
import re
from bs4 import BeautifulSoup

st.set_page_config(page_title="Opsify Dispute Automation Tool", page_icon="🛡️", layout="wide")

st.title("🛡️ Opsify Dispute Automation Tool")
st.write("Upload 3-Bureau Credit Report (PDF, HTML, or TXT) to parse negative items and generate dispute letters.")

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
    unattached_inquiries = []
    raw_text = ""

    # -------------------------------------------------------------
    # 1. TEXT EXTRACTION ENGINE
    # -------------------------------------------------------------
    if file_type == "pdf":
        with st.spinner("Reading PDF pages..."):
            with pdfplumber.open(uploaded_file) as pdf:
                for page in pdf.pages:
                    # Fallback to standard text extraction if layout text is empty
                    t = page.extract_text()
                    if t:
                        raw_text += t + "\n"
                    else:
                        # Try layout mode
                        t_layout = page.extract_text(layout=True)
                        if t_layout:
                            raw_text += t_layout + "\n"
    else:
        raw_text = uploaded_file.read().decode("utf-8", errors="ignore")

    # -------------------------------------------------------------
    # 2. BROAD PATTERN MATCHING / REGEX PARSER
    # -------------------------------------------------------------
    if raw_text.strip():
        lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
        
        # Keywords
        neg_words = ["CHARGE-OFF", "CHARGED OFF", "COLLECTION", "DELINQUENT", "PAST DUE", "REPOSSESSION", "FORECLOSURE", "DEROGATORY", "LATE 30", "LATE 60", "LATE 90", "LATE"]
        
        for idx, line in enumerate(lines):
            line_upper = line.upper()
            
            # --- Detect Negative Accounts ---
            if any(w in line_upper for w in neg_words):
                # Pull creditor name from adjacent line or current line
                creditor = lines[idx-1] if idx > 0 and len(lines[idx-1]) < 40 else line[:30]
                
                # Pull account number if available
                acct = "Check Report"
                acct_match = re.search(r'#?\b[A-Z0-9\*]{4,}\b', line)
                if acct_match:
                    acct = acct_match.group(0)

                negative_accounts.append({
                    "creditor": creditor,
                    "acct": acct,
                    "status": line[:50]
                })

            # --- Detect Inquiries ---
            if "INQUIRY" in line_upper or "INQUIRIES" in line_upper:
                if not any(ignore in line_upper for ignore in ["TYPE", "PERMISSIBLE", "SECTION", "TOTAL"]):
                    unattached_inquiries.append({
                        "creditor": line[:35],
                        "date": "See Report"
                    })

            # --- Detect Personal Info / Address ---
            if "ADDRESS" in line_upper and client_address.strip().lower() not in line.lower():
                if len(line) > 10 and not any(ignore in line_upper for ignore in ["TYPE", "HISTORY", "PERSONAL"]):
                    incorrect_addresses.append(line)

    # -------------------------------------------------------------
    # DASHBOARD DISPLAY
    # -------------------------------------------------------------
    st.success("Analysis complete!")

    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("📍 Incorrect Personal Info")
        if incorrect_addresses:
            for addr in set(incorrect_addresses):
                st.warning(f"Delete: {addr}")
        else:
            st.info("No extra addresses flagged.")

    with col2:
        st.subheader("🚨 Negative & Late Accounts")
        if negative_accounts:
            for acc in negative_accounts:
                st.error(f"**{acc['creditor']}**\n- Acct #: `{acc['acct']}`\n- Status: {acc['status']}")
        else:
            st.info("No derogatory or late accounts flagged.")

    with col3:
        st.subheader("🔎 Unattached Inquiries")
        if unattached_inquiries:
            for inq in unattached_inquiries:
                st.error(f"**{inq['creditor']}**\nDate: {inq['date']}")
        else:
            st.info("No unattached inquiries flagged.")

    st.markdown("---")

    # -------------------------------------------------------------
    # DEBUGGER / RAW TEXT INSPECTOR
    # -------------------------------------------------------------
    with st.expander("🔍 Debugger: Click to inspect parsed text from PDF"):
        if raw_text.strip():
            st.text_area("Extracted Raw Text", raw_text[:3000], height=200)
        else:
            st.error("⚠️ Warning: No text could be extracted from this PDF. This means the PDF might be an image/scanned copy without searchable text.")

    # -------------------------------------------------------------
    # DISPUTE LETTER GENERATOR
    # -------------------------------------------------------------
    st.subheader("📄 Generated Dispute Letter Preview")
    
    letter_text = f"FROM:\n{client_name}\n{client_address}\nDOB: {client_dob} | SSN (Last 4): {client_ssn}\n\n"
    letter_text += f"TO:\n{bureau} Dispute Department\n\n"
    letter_text += "SUBJECT: DEMAND FOR IMMEDIATE INVESTIGATION & REMOVAL OF INACCURATE DATA\n\n"
    letter_text += "To Whom It May Concern,\n\n"
    letter_text += "I am formally disputing the following inaccurate items appearing on my credit file pursuant to FCRA regulations.\n\n"

    if incorrect_addresses:
        letter_text += "1. INACCURATE PERSONAL INFORMATION:\n"
        for addr in set(incorrect_addresses):
            letter_text += f"   - DELETE ADDRESS: {addr}\n"
        letter_text += "\n"

    if negative_accounts:
        letter_text += "2. UNVERIFIED NEGATIVE / LATE ACCOUNTS (FCRA § 611):\n"
        for acc in negative_accounts:
            letter_text += f"   - Creditor: {acc['creditor']} | Acct #: {acc['acct']} | Detail: {acc['status']}\n"
        letter_text += "\n"

    if unattached_inquiries:
        letter_text += "3. UNAUTHORIZED HARD INQUIRIES (FCRA § 604):\n"
        for inq in unattached_inquiries:
            letter_text += f"   - Inquiry Creditor: {inq['creditor']}\n"
        letter_text += "\n"

    letter_text += "Please complete your reinvestigation within 30 days and provide an updated credit report.\n\n"
    letter_text += f"Sincerely,\n{client_name}"

    st.text_area("Review Letter Draft", letter_text, height=300)
    
    st.download_button(
        label="📥 Download Dispute Letter (.TXT)",
        data=letter_text,
        file_name=f"{client_name.replace(' ', '_')}_{bureau}_Dispute_Letter.txt",
        mime="text/plain"
    )
