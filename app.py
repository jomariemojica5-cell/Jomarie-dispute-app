import streamlit as st
from bs4 import BeautifulSoup
import re
from fpdf import FPDF

# Set Page Config
st.set_page_config(page_title="Opsify Credit Report Parser", page_icon="📑", layout="wide")

st.title("🛡️ Opsify Dispute Automation Tool")
st.write("Upload client's credit report HTML/Text file to instantly extract negative items and build dispute letters.")

# Sidebar for Client Info
st.sidebar.header("👤 Client Details")
client_name = st.sidebar.text_input("Client Full Name", "John Doe")
client_dob = st.sidebar.text_input("Date of Birth", "01/01/1990")
client_ssn = st.sidebar.text_input("SSN (Last 4)", "1234")
client_address = st.sidebar.text_area("Current Address", "123 Main St, City, ST 12345")
bureau = st.sidebar.selectbox("Select Target Bureau", ["Equifax", "Experian", "TransUnion"])

# File Uploader
uploaded_file = st.file_uploader("Upload Credit Report (HTML or TXT)", type=["html", "htm", "txt"])

if uploaded_file is not None:
    content = uploaded_file.read().decode("utf-8", errors="ignore")
    soup = BeautifulSoup(content, "html.parser")
    
    st.success("File uploaded successfully! Parsing data...")
    
    # -------------------------------------------------------------
    # PARSING ENGINE LOGIC
    # -------------------------------------------------------------
    incorrect_addresses = []
    negative_accounts = []
    positive_creditors = []
    unattached_inquiries = []
    
    # 1. Parse Addresses
    addr_elements = soup.find_all(class_=re.compile(r'address|prev-addr', re.I))
    for el in addr_elements:
        txt = el.get_text(strip=True)
        if client_address.strip().lower() not in txt.lower() and txt not in incorrect_addresses:
            incorrect_addresses.append(txt)

    # 2. Parse Accounts (Negative vs Positive)
    account_blocks = soup.find_all(class_=re.compile(r'account-row|tradeline', re.I))
    for block in account_blocks:
        creditor = block.find(class_=re.compile(r'creditor-name|account-name', re.I))
        status = block.find(class_=re.compile(r'account-status|status', re.I))
        acct_num = block.find(class_=re.compile(r'account-number|acct-num', re.I))
        
        c_name = creditor.get_text(strip=True) if creditor else "UNKNOWN CREDITOR"
        s_val = status.get_text(strip=True).upper() if status else ""
        a_num = acct_num.get_text(strip=True) if acct_num else "N/A"
        
        is_neg = any(k in s_val for k in ["COLLECTION", "CHARGE-OFF", "PAST DUE", "DELINQUENT", "LATE"])
        if is_neg:
            negative_accounts.append({"creditor": c_name, "acct": a_num, "status": s_val})
        else:
            positive_creditors.append(c_name.upper())

    # 3. Parse Unattached Hard Inquiries
    inquiry_blocks = soup.find_all(class_=re.compile(r'inquiry-row|inquiry-item', re.I))
    for inq in inquiry_blocks:
        cred = inq.find(class_=re.compile(r'inquiry-name|creditor', re.I))
        date = inq.find(class_=re.compile(r'inquiry-date|date', re.I))
        
        c_txt = cred.get_text(strip=True).upper() if cred else ""
        d_txt = date.get_text(strip=True) if date else "N/A"
        
        if c_txt:
            matched = any(pos in c_txt or c_txt in pos for pos in positive_creditors)
            if not matched:
                unattached_inquiries.append({"creditor": c_txt, "date": d_txt})

    # -------------------------------------------------------------
    # DASHBOARD DISPLAY (3 Columns Layout)
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
                st.error(f"**{acc['creditor']}**\nAcct: {acc['acct']} | Status: {acc['status']}")
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
    # AUTOMATED LETTER GENERATOR
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
            letter_text += f"   - Please DELETE Address: {addr}\n"
        letter_text += "\n"

    if negative_accounts:
        letter_text += "2. UNVERIFIED NEGATIVE ACCOUNTS (FCRA § 611):\n"
        for acc in negative_accounts:
            letter_text += f"   - Creditor: {acc['creditor']} | Acct #: {acc['acct']} | Reported Status: {acc['status']}\n"
        letter_text += "\n"

    if unattached_inquiries:
        letter_text += "3. UNAUTHORIZED HARD INQUIRIES (FCRA § 604 - Lack of Permissible Purpose):\n"
        for inq in unattached_inquiries:
            letter_text += f"   - Inquiry: {inq['creditor']} | Date: {inq['date']}\n"
        letter_text += "\n"

    letter_text += "Please conduct a full reinvestigation within 30 days and provide an updated credit report.\n\n"
    letter_text += f"Sincerely,\n{client_name}"

    st.text_area("Review Letter Draft", letter_text, height=300)
    
    # Download Button
    st.download_button(
        label="📥 Download Dispute Letter (.TXT)",
        data=letter_text,
        file_name=f"{client_name.replace(' ', '_')}_{bureau}_Dispute_Letter.txt",
        mime="text/plain"
    )
