import streamlit as st
from bs4 import BeautifulSoup
import re
import pdfplumber

st.set_page_config(page_title="Opsify Credit Report Parser", page_icon="🛡️", layout="wide")

st.title("🛡️ Opsify Dispute Automation Tool")
st.write("Upload client's credit report (PDF, HTML, or TXT) to instantly extract negative items and build dispute letters.")

# Sidebar
st.sidebar.header("👤 Client Details")
client_name = st.sidebar.text_input("Client Full Name", "Sophia Baker")
client_dob = st.sidebar.text_input("Date of Birth", "09/07/1974")
client_ssn = st.sidebar.text_input("SSN (Last 4)", "9139")
client_address = st.sidebar.text_area("Current Address", "1119 Madison St, Bogalusa Louisiana 70427")
bureau = st.sidebar.selectbox("Select Target Bureau", ["Experian", "Equifax", "TransUnion"])

uploaded_file = st.file_uploader("Upload Credit Report (PDF, HTML, or TXT)", type=["pdf", "html", "htm", "txt"])

if uploaded_file is not None:
    file_type = uploaded_file.name.split(".")[-1].lower()
    raw_text = ""
    
    incorrect_addresses = []
    negative_accounts = []
    unattached_inquiries = []

    # -------------------------------------------------------------
    # 1. PDF PARSER ENGINE (pdfplumber)
    # -------------------------------------------------------------
    if file_type == "pdf":
        with pdfplumber.open(uploaded_file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    raw_text += page_text + "\n"
        
        # Split text into chunks/lines
        lines = raw_text.split("\n")
        
        for i, line in enumerate(lines):
            line_upper = line.upper()
            
            # --- Detect Negative Accounts ---
            neg_keywords = ["COLLECTION", "CHARGE-OFF", "CHARGED OFF", "REPOSSESSION", "FORECLOSURE", "PAST DUE", "DELINQUENT", "LATE 30", "LATE 60", "LATE 90", "DEROGATORY"]
            if any(kw in line_upper for kw in neg_keywords):
                # Context extraction: Kunin ang katabing linya para sa Creditor Name
                creditor_name = lines[i-1].strip() if i > 0 else "Unknown Creditor"
                if len(creditor_name) < 3 or any(kw in creditor_name.upper() for kw in neg_keywords):
                    creditor_name = line[:25]
                
                # Extract Account Number
                acct_match = re.search(r'#?\b[A-Z0-9*]{4,}\b', line)
                acct_no = acct_match.group(0) if acct_match else "Unverified/N/A"
                
                negative_accounts.append({
                    "creditor": creditor_name,
                    "acct": acct_no,
                    "status": line_upper[:40]
                })

            # --- Detect Hard Inquiries ---
            if "INQUIRY" in line_upper or "INQUIRIES" in line_upper or re.search(r'\b(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+\d{1,2},\s+20\d{2}\b', line_upper):
                if not any(header in line_upper for header in ["PERMISSIBLE", "TYPES OF INQUIRIES", "RECORD OF INQUIRIES"]):
                    inq_date_match = re.search(r'\d{2}/\d{2}/\d{4}', line)
                    inq_date = inq_date_match.group(0) if inq_date_match else "N/A"
                    unattached_inquiries.append({
                        "creditor": line[:30].strip(),
                        "date": inq_date
                    })

            # --- Detect Previous Addresses ---
            if "ADDRESS" in line_upper or "PRIOR ADDRESS" in line_upper:
                if client_address.strip().lower() not in line.lower():
                    clean_addr = re.sub(r'ADDRESS|PRIOR|PREVIOUS', '', line, flags=re.I).strip()
                    if len(clean_addr) > 8 and clean_addr not in incorrect_addresses:
                        incorrect_addresses.append(clean_addr)

    # -------------------------------------------------------------
    # 2. HTML PARSER ENGINE (BS4)
    # -------------------------------------------------------------
    elif file_type in ["html", "htm"]:
        content = uploaded_file.read().decode("utf-8", errors="ignore")
        soup = BeautifulSoup(content, "html.parser")
        
        # HTML Extraction Logic
        account_blocks = soup.find_all(class_=re.compile(r'account-row|tradeline', re.I))
        for block in account_blocks:
            creditor = block.find(class_=re.compile(r'creditor-name|account-name', re.I))
            status = block.find(class_=re.compile(r'account-status|status', re.I))
            acct_num = block.find(class_=re.compile(r'account-number|acct-num', re.I))
            
            c_name = creditor.get_text(strip=True) if creditor else "UNKNOWN CREDITOR"
            s_val = status.get_text(strip=True).upper() if status else ""
            a_num = acct_num.get_text(strip=True) if acct_num else "N/A"
            
            if any(k in s_val for k in ["COLLECTION", "CHARGE-OFF", "PAST DUE", "DELINQUENT", "LATE"]):
                negative_accounts.append({"creditor": c_name, "acct": a_num, "status": s_val})

    st.success("File parsed successfully!")

    # -------------------------------------------------------------
    # DASHBOARD DISPLAY
    # -------------------------------------------------------------
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("📍 Incorrect Addresses")
        if incorrect_addresses:
            for addr in incorrect_addresses:
                st.warning(f"Delete: {addr}")
        else:
            st.info("No extra addresses flagged.")

    with col2:
        st.subheader("🚨 Negative Accounts")
        if negative_accounts:
            for acc in negative_accounts:
                st.error(f"**{acc['creditor']}**\nAcct #: {acc['acct']}\nStatus: {acc['status']}")
        else:
            st.info("No negative accounts flagged.")

    with col3:
        st.subheader("🔎 Unattached Inquiries")
        if unattached_inquiries:
            for inq in unattached_inquiries:
                st.error(f"**{inq['creditor']}**\nDate: {inq['date']}")
        else:
            st.info("No unattached inquiries flagged.")

    st.markdown("---")

    # -------------------------------------------------------------
    # LETTER GENERATOR
    # -------------------------------------------------------------
    st.subheader("📄 Generated Dispute Letter Preview")
    
    letter_text = f"FROM:\n{client_name}\n{client_address}\nDOB: {client_dob} | SSN (Last 4): {client_ssn}\n\n"
    letter_text += f"TO:\n{bureau} Dispute Department\n\n"
    letter_text += "SUBJECT: DEMAND FOR IMMEDIATE REMOVAL OF INACCURATE & UNAUTHORIZED ITEMS\n\n"
    letter_text += "To Whom It May Concern,\n\n"
    letter_text += "I am formally disputing the following inaccurate, unverified, and unauthorized information on my credit report pursuant to FCRA regulations.\n\n"

    if incorrect_addresses:
        letter_text += "1. INACCURATE PERSONAL INFORMATION:\n"
        for addr in incorrect_addresses:
            letter_text += f"   - Delete Address: {addr}\n"
        letter_text += "\n"

    if negative_accounts:
        letter_text += "2. UNVERIFIED NEGATIVE ACCOUNTS (FCRA § 611):\n"
        for acc in negative_accounts:
            letter_text += f"   - Creditor: {acc['creditor']} | Acct #: {acc['acct']} | Status: {acc['status']}\n"
        letter_text += "\n"

    if unattached_inquiries:
        letter_text += "3. UNAUTHORIZED HARD INQUIRIES (FCRA § 604):\n"
        for inq in unattached_inquiries:
            letter_text += f"   - Inquiry: {inq['creditor']} | Date: {inq['date']}\n"
        letter_text += "\n"

    letter_text += "Please conduct a full reinvestigation within 30 days and provide an updated credit report.\n\n"
    letter_text += f"Sincerely,\n{client_name}"

    st.text_area("Review Letter Draft", letter_text, height=300)
    
    st.download_button(
        label="📥 Download Dispute Letter (.TXT)",
        data=letter_text,
        file_name=f"{client_name.replace(' ', '_')}_{bureau}_Dispute_Letter.txt",
        mime="text/plain"
    )
