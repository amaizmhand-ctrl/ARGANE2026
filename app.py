import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import datetime
import json
import random
import time
import io
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date, timedelta

# Supabase Client Import
try:
    from supabase import create_client, Client
    HAS_SUPABASE_LIB = True
except ImportError:
    HAS_SUPABASE_LIB = False

def get_supabase():
    if not HAS_SUPABASE_LIB:
        return None
    url = st.secrets.get("SUPABASE_URL", "")
    key = st.secrets.get("SUPABASE_KEY", "")
    if url and key:
        try:
            return create_client(url, key)
        except Exception:
            return None
    return None

# ---------------------------------------------------------
# Page Configuration & Full Dark Mode CSS Styling
# ---------------------------------------------------------
st.set_page_config(
    page_title="Lqargane - المنظومة الذكية لإدارة المواظبة والزمن المدرسي",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800;900&display=swap');
    
    html, body, .stApp {
        background-color: #0b132b !important;
        font-family: 'Tajawal', sans-serif !important;
        direction: rtl;
        text-align: right;
        color: #f8fafc !important;
    }
    
    h1, h2, h3, h4, h5, h6 {
        color: #38bdf8 !important;
        font-weight: 800 !important;
    }
    
    p, span, label, div, li, td, th {
        color: #f1f5f9 !important;
    }
    
    .highlight-yellow {
        color: #facc15 !important;
        font-weight: 700;
    }

    .highlight-green {
        color: #4ade80 !important;
        font-weight: 700;
    }

    .alert-box {
        background-color: #7f1d1d !important;
        border: 2px solid #ef4444 !important;
        padding: 15px;
        border-radius: 10px;
        color: #f8fafc !important;
        font-size: 1.1rem;
        font-weight: bold;
        margin-bottom: 15px;
    }

    .success-box {
        background-color: #064e3b !important;
        border: 2px solid #10b981 !important;
        padding: 15px;
        border-radius: 10px;
        color: #f8fafc !important;
        font-size: 1.1rem;
        font-weight: bold;
        margin-bottom: 15px;
    }

    input, select, textarea, div[data-baseweb="input"], div[data-baseweb="select"] {
        background-color: #1c2541 !important;
        color: #ffffff !important;
        border: 1px solid #3a506b !important;
        border-radius: 8px !important;
    }
    
    input:focus, textarea:focus {
        border-color: #38bdf8 !important;
        box-shadow: 0 0 8px rgba(56, 189, 248, 0.4) !important;
    }

    .stButton>button {
        border-radius: 10px;
        font-weight: 700;
        background: linear-gradient(135deg, #0284c7, #0369a1) !important;
        color: #ffffff !important;
        border: 1px solid #38bdf8 !important;
        box-shadow: 0 4px 12px rgba(2, 132, 199, 0.3);
        transition: all 0.2s ease;
    }
    
    .stButton>button:hover {
        background: linear-gradient(135deg, #0369a1, #075985) !important;
        color: #facc15 !important;
        transform: translateY(-2px);
    }

    section[data-testid="stSidebar"] {
        background-color: #0b132b !important;
        border-left: 1px solid #1c2541 !important;
    }
    
    section[data-testid="stSidebar"] * {
        color: #f8fafc !important;
    }

    div[data-aria-label="Grid"], .stDataFrame {
        background-color: #1c2541 !important;
        color: #ffffff !important;
        border-radius: 10px;
        border: 1px solid #3a506b;
    }

    .time-badge {
        background-color: #1c2541;
        border: 1px solid #38bdf8;
        padding: 6px 12px;
        border-radius: 8px;
        color: #facc15;
        font-weight: bold;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# Database Initialization & Management
# ---------------------------------------------------------
DB_FILE = "school_absence.db"

def get_db_connection():
    conn = sqlite3.connect(DB_FILE, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            full_name TEXT,
            role TEXT,
            custom_title TEXT DEFAULT 'أستاذ(ة)',
            status TEXT DEFAULT 'active',
            assigned_class TEXT DEFAULT '',
            phone TEXT UNIQUE,
            email TEXT DEFAULT '',
            must_change_password INTEGER DEFAULT 0,
            last_seen TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_name TEXT UNIQUE,
            level TEXT DEFAULT '',
            branch TEXT DEFAULT ''
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_number INTEGER,
            massar_id TEXT UNIQUE,
            full_name TEXT,
            class_name TEXT,
            guardian_phone TEXT DEFAULT '',
            secret_code TEXT,
            total_absent_hours INTEGER DEFAULT 0,
            attendance_points INTEGER DEFAULT 100
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS absence_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            class_name TEXT,
            date TEXT,
            session_number INTEGER,
            session_time TEXT,
            recorded_by TEXT,
            subject TEXT DEFAULT '',
            note TEXT,
            FOREIGN KEY (student_id) REFERENCES students (id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS teacher_timetable (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_username TEXT,
            class_name TEXT,
            day_of_week TEXT,
            session_number INTEGER,
            subject TEXT DEFAULT 'المعلوماتية'
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS staff_chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_name TEXT,
            sender_title TEXT,
            message TEXT,
            timestamp TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS flash_announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            message TEXT,
            expiry_date TEXT,
            publisher TEXT,
            created_at TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS student_disciplinary_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            issuer_title TEXT,
            notice_type TEXT,
            content TEXT,
            created_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS entry_permits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            issued_by TEXT,
            reason TEXT,
            timestamp TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS login_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            full_name TEXT,
            role TEXT,
            action TEXT,
            timestamp TEXT
        )
    ''')

    dev_pass = st.secrets.get("DEV_PASSWORD", "dev1234")
    dev_email = st.secrets.get("DEV_EMAIL", "amaizmhand@gmail.com")
    
    c.execute("SELECT * FROM users WHERE role = 'developer'")
    existing_dev = c.fetchone()
    if not existing_dev:
        c.execute('''
            INSERT INTO users (username, password, full_name, role, custom_title, status, phone, email)
            VALUES ('dev_admin', ?, 'المطور الرئيسي', 'developer', 'مطور النظام', 'active', '0600000000', ?)
        ''', (dev_pass, dev_email))
    else:
        c.execute("UPDATE users SET username = 'dev_admin', email = ?, password = ? WHERE role = 'developer'", (dev_email, dev_pass))

    conn.commit()
    conn.close()

init_db()

SESSIONS = {
    1: {"name": "الحصة 1 (الصباحية)", "time": "08:00 - 09:00", "period": "صباح"},
    2: {"name": "الحصة 2 (الصباحية)", "time": "09:00 - 10:00", "period": "صباح"},
    3: {"name": "الحصة 3 (الصباحية)", "time": "10:00 - 11:00", "period": "صباح"},
    4: {"name": "الحصة 4 (الصباحية)", "time": "11:00 - 12:00", "period": "صباح"},
    5: {"name": "الحصة 5 (المسائية)", "time": "14:00 - 15:00", "period": "مساء"},
    6: {"name": "الحصة 6 (المسائية)", "time": "15:00 - 16:00", "period": "مساء"},
    7: {"name": "الحصة 7 (المسائية)", "time": "16:00 - 17:00", "period": "مساء"},
    8: {"name": "الحصة 8 (المسائية)", "time": "17:00 - 18:00", "period": "مساء"},
}

PRESET_NOTES = [
    "حاضر ومواظب ومنضبط",
    "تغيب بدون إذن مسبق",
    "تأخر غير مبرر عن بداية الحصة",
    "سلوك غير مقبول وتشويش داخل الفصل",
    "عدم إحضار اللوازم والكتب المدرسيّة",
    "مشاركة ممتازة والتزام بالهندام المدرسي"
]

def log_activity(username, full_name, role, action):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO login_logs (username, full_name, role, action, timestamp) VALUES (?, ?, ?, ?, ?)",
              (username, full_name, role, action, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    c.execute("UPDATE users SET last_seen = ? WHERE username = ?", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), username))
    conn.commit()
    conn.close()

def send_email_notification(to_email, subject, body):
    try:
        sender_email = st.secrets.get("SMTP_EMAIL", "").strip()
        sender_password = st.secrets.get("SMTP_PASSWORD", "").replace(" ", "").strip()
        
        if not sender_email or not sender_password:
            return False

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = to_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        text = msg.as_string()
        server.sendmail(sender_email, to_email, text)
        server.quit()
        return True
    except Exception:
        return False

def send_otp_email(to_email, otp_code):
    body = f"مرحباً محند،\n\nرمز التحقق الثنائي الخاص بك للدخول إلى منظومة Lqargane هو: {otp_code}\n\nهذا الرمز صالح لهذه الجلسة فقط."
    success = send_email_notification(to_email, "Lqargane - رمز المصادقة الثنائية (2FA)", body)
    if not success:
        st.toast(f"🔐 [كود التحقق 2FA] الكود الخاص بك هو: {otp_code}", icon="🛡️")
    return True

if "user" not in st.session_state:
    st.session_state.user = None
if "pending_2fa_user" not in st.session_state:
    st.session_state.pending_2fa_user = None
if "generated_otp" not in st.session_state:
    st.session_state.generated_otp = None
if "forgot_password_mode" not in st.session_state:
    st.session_state.forgot_password_mode = False

def logout():
    if st.session_state.user:
        log_activity(st.session_state.user.get('username', 'parent'), st.session_state.user.get('full_name', ''), st.session_state.user.get('role', ''), "تسجيل الخروج")
    st.session_state.user = None
    st.session_state.pending_2fa_user = None
    st.session_state.generated_otp = None
    if "active_parent_student" in st.session_state:
        del st.session_state["active_parent_student"]
    st.rerun()

# ---------------------------------------------------------
# Sidebar Navigation & Login Flow
# ---------------------------------------------------------
with st.sidebar:
    st.markdown("<h2 style='text-align: center; color: #38bdf8;'>🏫 Lqargane</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #facc15; font-size: 0.85rem;'>منصة المواظبة والزمن المدرسي الذكي</p>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #38bdf8; font-size: 0.8rem; font-weight: bold;'>By: Pr:M'h.AMAIZ</p>", unsafe_allow_html=True)
    
    now_str = datetime.now().strftime("%Y-%m-%d | %H:%M:%S")
    st.markdown(f"<div style='text-align:center;' class='time-badge'>⏱️ {now_str}</div>", unsafe_allow_html=True)
    st.divider()

    if st.session_state.user:
        u = st.session_state.user
        role_label = u.get('custom_title', u['role'])

        st.markdown(f"**مرحباً بك:** <span class='highlight-yellow'>{u['full_name']}</span>", unsafe_allow_html=True)
        st.markdown(f"**الصفة التربوية:** `{role_label}`")

        if u['role'] != 'parent':
            with st.expander("⚙️ إعدادات الحساب (كلمة السر والهاتف)"):
                new_phone = st.text_input("تحديث رقم الهاتف", value=u.get('phone', ''))
                pwd_old = st.text_input("كلمة السر الحالية", type="password", key="pwd_old_sub")
                pwd_new = st.text_input("كلمة السر الجديدة", type="password", key="pwd_new_sub")
                
                if st.button("حفظ التعديلات الشخصية", key="btn_update_profile_self"):
                    conn = get_db_connection()
                    c = conn.cursor()
                    if pwd_old and pwd_new:
                        c.execute("SELECT password FROM users WHERE username = ?", (u['username'],))
                        res_p = c.fetchone()
                        if res_p and res_p['password'] == pwd_old:
                            c.execute("UPDATE users SET password = ?, phone = ? WHERE username = ?", (pwd_new, new_phone, u['username']))
                            conn.commit()
                            st.success("تم تحديث كلمة المرور ورقم الهاتف بنجاح!")
                        else:
                            st.error("كلمة المرور الحالية غير صحيحة.")
                    else:
                        c.execute("UPDATE users SET phone = ? WHERE username = ?", (new_phone, u['username']))
                        conn.commit()
                        st.success("تم تحديث رقم الهاتف بنجاح!")
                    conn.close()

        st.divider()
        if st.button("🚪 تسجيل الخروج الآمن", use_container_width=True, type="primary"):
            logout()
            
    elif st.session_state.pending_2fa_user:
        st.subheader("🛡️ المصادقة الثنائية (2FA)")
        st.info("أدخل كود التحقق السري المكون من 6 أرقام (يصلك بالبريد أو يظهر في الشاشة):")
        
        entered_otp = st.text_input("كود التحقق:", type="password", max_chars=6)
        
        col_v1, col_v2 = st.columns(2)
        with col_v1:
            if st.button("تأكيد الدخول", use_container_width=True, type="primary"):
                if entered_otp == st.session_state.generated_otp:
                    st.session_state.user = st.session_state.pending_2fa_user
                    log_activity(st.session_state.user['username'], st.session_state.user['full_name'], st.session_state.user['role'], "تسجيل الدخول الناجح عبر 2FA")
                    st.session_state.pending_2fa_user = None
                    st.session_state.generated_otp = None
                    st.success("تم التحقق بنجاح!")
                    st.rerun()
                else:
                    st.error("كود التحقق غير صحيح!")
        with col_v2:
            if st.button("إلغاء", use_container_width=True):
                st.session_state.pending_2fa_user = None
                st.session_state.generated_otp = None
                st.rerun()

    else:
        auth_mode = st.radio("طريقة الدخول:", ["🔐 دخول الأطر (مع 2FA الآمن)", "👁️ تلميذ / ولي أمر"], label_visibility="collapsed")

        if auth_mode == "🔐 دخول الأطر (مع 2FA الآمن)":
            if not st.session_state.forgot_password_mode:
                st.subheader("دخول الأطر التربوية الآمن")
                login_id = st.text_input("المعرف أو الهاتف أو البريد المهني", key="login_id_field")
                login_pass = st.text_input("كلمة المرور / الكود", type="password", key="login_pass_field")
                
                if st.button("إرسال كود المصادقة الثنائية", use_container_width=True, type="primary"):
                    conn = get_db_connection()
                    c = conn.cursor()
                    c.execute("SELECT * FROM users WHERE (username = ? OR phone = ? OR email = ?) AND password = ?", (login_id, login_id, login_id, login_pass))
                    user = c.fetchone()
                    conn.close()

                    if user:
                        if user['status'] == 'active':
                            otp = str(random.randint(100000, 999999))
                            st.session_state.generated_otp = otp
                            st.session_state.pending_2fa_user = dict(user)
                            
                            target_mail = user['email'] if user['email'] else st.secrets.get("DEV_EMAIL", "amaizmhand@gmail.com")
                            send_otp_email(target_mail, otp)
                            st.success("تم توليد كود التحقق الثنائي بنجاح!")
                            st.rerun()
                        else:
                            st.warning("حسابك غير مفعل حالياً.")
                    else:
                        st.error("معلومات الدخول غير صحيحة!")

                st.markdown("---")
                if st.button("🔑 نسيت كلمة المرور؟", use_container_width=True):
                    st.session_state.forgot_password_mode = True
                    st.rerun()
            else:
                st.subheader("🔄 استرجاع كلمة المرور للأطر")
                st.info("أدخل بريدك الإلكتروني أو معرفك المسجل بالمنظومة لتعيين كلمة مرور مؤحدة جديدة.")
                f_id = st.text_input("البريد الإلكتروني أو المعرف:", key="forgot_id_input")
                
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    if st.button("إرسال كلمة السر الجديدة", type="primary"):
                        if f_id:
                            conn = get_db_connection()
                            c = conn.cursor()
                            c.execute("SELECT * FROM users WHERE username = ? OR email = ? OR phone = ?", (f_id, f_id, f_id))
                            staff_user = c.fetchone()
                            
                            if staff_user and staff_user['role'] != 'developer':
                                # تعيين كلمة مرور موحدة تلقائياً
                                new_unified_pass = random.choice(["2026@2027", "Admin2027@"])
                                c.execute("UPDATE users SET password = ? WHERE id = ?", (new_unified_pass, staff_user['id']))
                                conn.commit()
                                
                                # إرسال رسالة للمطور
                                dev_email = st.secrets.get("DEV_EMAIL", "amaizmhand@gmail.com")
                                dev_msg = f"تنبيه أمني:\nالإطار {staff_user['full_name']} ({staff_user['username']}) طلب استرجاع كلمة المرور.\nتم تعيين كلمة سر مؤحدة له: {new_unified_pass}"
                                send_email_notification(dev_email, f"Lqargane - استرجاع كلمة المرور للإطار {staff_user['full_name']}", dev_msg)
                                
                                # إرسال رسالة للإطار بريده
                                if staff_user['email']:
                                    staff_msg = f"مرحباً {staff_user['full_name']},\n\nلقد تم إعادة تعيين كلمة المرور الخاصة بك في منصة Lqargane بنجاح بناءً على طلبك.\nكلمة المرور المؤقتة الخاصة بك هي: {new_unified_pass}\n\nيمكنك استخدامها للدخول ثم تعديلها من إعدادات حسابك."
                                    send_email_notification(staff_user['email'], "Lqargane - كلمة المرور الجديدة", staff_msg)
                                    
                                st.success("تم إرسال كلمة المرور المؤقتة لبريدك الإلكتروني بنجاح وإشعار المطور!")
                            else:
                                st.error("الحساب غير موجود أو غير مسموح بهذه العملية.")
                            conn.close()
                        else:
                            st.error("يرجى إدخال المعرف أو البريد.")
                with col_f2:
                    if st.button("الرجوع للدخول"):
                        st.session_state.forgot_password_mode = False
                        st.rerun()

        elif auth_mode == "👁️ تلميذ / ولي أمر":
            st.subheader("بوابة المراقبة الفردية")
            p_massar = st.text_input("رقم مسار التلميذ(ة)", placeholder="مثال: G123456789").strip()
            p_code = st.text_input("الرمز السري (رقم مسار + 2026)", type="password").strip()
            
            if st.button("عرض سجل الغياب والملاحظات", use_container_width=True, type="primary"):
                if p_massar and p_code:
                    conn = get_db_connection()
                    c = conn.cursor()
                    c.execute("SELECT * FROM students WHERE massar_id = ? AND secret_code = ?", (p_massar, p_code))
                    student = c.fetchone()
                    conn.close()

                    if student:
                        st.session_state.active_parent_student = dict(student)
                        st.session_state.user = {"role": "parent", "full_name": student['full_name'], "custom_title": "ولي أمر / تلميذ"}
                        log_activity(student['massar_id'], student['full_name'], "parent", "دخول فضاء التلميذ/الولي")
                        st.success("تم الدخول بنجاح!")
                        st.rerun()
                    else:
                        st.error("رقم مسار أو الرمز السري غير صحيح!")
                else:
                    st.error("يرجى ملء كافة الخانات.")

# ---------------------------------------------------------
# Flash Announcements Banner
# ---------------------------------------------------------
if st.session_state.user:
    conn = get_db_connection()
    today_str = date.today().strftime("%Y-%m-%d")
    announcements = pd.read_sql_query("SELECT title, message, publisher FROM flash_announcements WHERE expiry_date >= ?", conn, params=(today_str,))
    conn.close()

    if not announcements.empty and st.session_state.user['role'] == 'parent':
        st.markdown("### 📢 إخبارات عاجلة وتنبيهات المؤسسة:")
        for _, ann in announcements.iterrows():
            st.warning(f"🚨 **{ann['title']}** (ناشر الخبر: {ann['publisher']})\n\n{ann['message']}")

# ---------------------------------------------------------
# Main Router
# ---------------------------------------------------------
if not st.session_state.user:
    st.markdown("""
        <div style="text-align: center; padding: 2.5rem; background: linear-gradient(135deg, #1c2541, #0b132b); border: 1px solid #3a506b; border-radius: 16px; color: white; margin-bottom: 2rem;">
            <h1 style="font-size: 2.5rem; margin-bottom: 0.5rem; color: #38bdf8;">🏫 منصة Lqargane الذكية لتتبع الغياب</h1>
            <p style="font-size: 1.2rem; color: #facc15;">موقع وتطبيق رسمي متزامن لحظياً لإدارة الزمن المدرسي ومتابعة المواظبة والسلوك</p>
            <p style="font-size: 1rem; color: #38bdf8; margin-top: 1rem; font-weight: bold;">Developed by: Pr:M'h.AMAIZ</p>
        </div>
    """, unsafe_allow_html=True)
    st.info("👈 يرجى تسجيل الدخول عبر الشريط الجانبي لتفعيل الحماية والولوج.")

else:
    role = st.session_state.user['role']

    # =========================================================
    # 1. DEVELOPER ROLE (المطور الرئيسي)
    # =========================================================
    if role == 'developer':
        st.markdown(f"""
            <div style="background: linear-gradient(135deg, #1e293b, #0f172a); padding: 1.5rem; border-radius: 12px; border: 1px solid #38bdf8; margin-bottom: 1.5rem;">
                <h2 style="color: #38bdf8; margin: 0;">🌟 أهلاً بك يا مطور النظام الرائع، <span style="color: #facc15;">{st.session_state.user['full_name']}</span></h2>
                <p style="color: #cbd5e1; margin-top: 5px;">صفحتك الرسمية للإشراف التقني الشامل على منظومة Lqargane والمتابعة الفورية للأنشطة.</p>
            </div>
        """, unsafe_allow_html=True)
        
        dev_tabs = st.tabs([
            "👤 إدارة الأطر والحسابات", 
            "📥 استيراد الإكسيل وتحليله", 
            "📊 سجلات الولوج والنشاطات", 
            "📅 استعمال الزمن", 
            "📄 نموذج استيراد الأطر (Excel)", 
            "🔑 إدارة وحذف الحسابات"
        ])

        conn = get_db_connection()

        with dev_tabs[0]:
            st.subheader("إضافة وإدارة حسابات الأطر التربوية والإدارية")
            d_name = st.text_input("الاسم الكامل")
            d_email = st.text_input("البريد الإلكتروني المهني")
            d_phone = st.text_input("رقم الهاتف", placeholder="06XXXXXXXX")
            d_role = st.selectbox("الدور الأساسي", ["teacher", "admin", "supervisor"], format_func=lambda x: {"teacher": "أستاذ(ة)", "admin": "المدير", "supervisor": "الحارس العام"}[x])
            d_custom_title = st.text_input("الصفة الدقيقة:", placeholder="مثال: الحارس العام للخارجية / أستاذ المعلوماتية")
            d_pass = st.text_input("الكود الأولي", value="123456")

            if st.button("حفظ الحساب بأمان", type="primary"):
                if d_name and d_email:
                    try:
                        c = conn.cursor()
                        c.execute("INSERT INTO users (username, password, full_name, role, custom_title, status, phone, email, must_change_password) VALUES (?, ?, ?, ?, ?, 'active', ?, ?, 1)",
                                  (d_email, d_pass, d_name, d_role, d_custom_title, d_phone, d_email))
                        conn.commit()
                        st.success("تم الحفظ بنجاح وتفعيل الحساب!")
                    except Exception as e:
                        st.error(f"خطأ: {e}")
                else:
                    st.error("يرجى ملء كافة الخانات.")
            
            st.divider()
            st.subheader("قائمة الأطر والأساتذة المسجلين")
            st.dataframe(pd.read_sql_query("SELECT id, username, full_name, role, custom_title, phone, email, last_seen FROM users", conn), use_container_width=True)

        with dev_tabs[1]:
            st.subheader("📥 قراءة واستيراد ملف الإكسيل الرسمي للتلاميذ وتحليله أونلاين")
            up_file = st.file_uploader("اختر ملف إكسيل الأقسام (.xlsx)", type=['xlsx'])
            if up_file:
                try:
                    xls = pd.ExcelFile(up_file)
                    st.write(f"📁 تم العثور على {len(xls.sheet_names)} قسم/مجموعة في الملف.")
                    
                    if st.button("معالجة واستيراد كافة أقسام ومجموعات التلاميذ"):
                        c = conn.cursor()
                        total_imported = 0
                        for sheet in xls.sheet_names:
                            df_sheet = pd.read_excel(up_file, sheet_name=sheet, header=None)
                            level_val = "تعليم ثانوي"
                            class_val = sheet
                            for r in range(min(10, df_sheet.shape[0])):
                                row_str = str(df_sheet.iloc[r].values)
                                if 'المستوى' in row_str:
                                    for val in df_sheet.iloc[r].values:
                                        if pd.notna(val) and 'المستوى' not in str(val) and ':' not in str(val):
                                            level_val = str(val).strip()
                                if 'القسم' in row_str:
                                    for val in df_sheet.iloc[r].values:
                                        if pd.notna(val) and 'القسم' not in str(val) and ':' not in str(val):
                                            class_val = str(val).strip()

                            branch_val = "علوم" if "علوم" in level_val or "علوم" in class_val else "آداب وعلوم إنسانية"
                            c.execute("INSERT OR IGNORE INTO classes (class_name, level, branch) VALUES (?, ?, ?)", (class_val, level_val, branch_val))
                            
                            df_students = pd.read_excel(up_file, sheet_name=sheet, skiprows=8)
                            if df_students.shape[1] >= 4:
                                for _, row in df_students.iterrows():
                                    massar = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""
                                    if massar and massar != 'nan' and massar != 'الرمز':
                                        family_name = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else ""
                                        first_name = str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else ""
                                        full_name = f"{family_name} {first_name}".strip()
                                        std_num = int(row.iloc[0]) if pd.notna(row.iloc[0]) and str(row.iloc[0]).isdigit() else 1
                                        secret_code = f"{massar}2026"
                                        
                                        c.execute("""
                                            INSERT INTO students (student_number, massar_id, full_name, class_name, secret_code) 
                                            VALUES (?, ?, ?, ?, ?) 
                                            ON CONFLICT(massar_id) DO UPDATE SET full_name=excluded.full_name, class_name=excluded.class_name
                                        """, (std_num, massar, full_name, class_val, secret_code))
                                        total_imported += 1
                        conn.commit()
                        st.success(f"🎉 تم بنجاح استيراد وتسجيل {total_imported} تلميذاً عبر الأقسام والمستويات!")
                except Exception as e:
                    st.error(f"خطأ أثناء القراءة: {e}")

        with dev_tabs[2]:
            st.subheader("📊 سجلات المتصفحين والداخلين ومواظبة الأساتذة")
            logs_df = pd.read_sql_query("SELECT username, full_name, role, action, timestamp FROM login_logs ORDER BY id DESC LIMIT 50", conn)
            st.dataframe(logs_df, use_container_width=True)

        with dev_tabs[3]:
            st.subheader("إدخال وتوزيع استعمال الزمن للأساتذة")
            teachers_df = pd.read_sql_query("SELECT full_name, username, custom_title FROM users WHERE role = 'teacher'", conn)
            classes_df = pd.read_sql_query("SELECT class_name FROM classes", conn)
            t_map = {f"{r['full_name']} ({r['custom_title']})": r['username'] for _, r in teachers_df.iterrows()}
            sel_t = st.selectbox("الأستاذ:", list(t_map.keys()) if t_map else [])
            sel_cls = st.selectbox("القسم أو المجموعة:", classes_df['class_name'].tolist() if not classes_df.empty else [])
            sel_day = st.selectbox("اليوم:", ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت"])
            sel_sess = st.selectbox("الحصة:", options=list(SESSIONS.keys()), format_func=lambda x: f"الحصة {x} ({SESSIONS[x]['time']})")
            sel_subj = st.text_input("المادة الدراسية:", value="المعلوماتية")

            if st.button("إضافة الحصة"):
                if sel_t and sel_cls:
                    c = conn.cursor()
                    c.execute("INSERT INTO teacher_timetable (teacher_username, class_name, day_of_week, session_number, subject) VALUES (?, ?, ?, ?, ?)",
                              (t_map[sel_t], sel_cls, sel_day, sel_sess, sel_subj))
                    conn.commit()
                    st.success("تمت الإضافة بنجاح.")

        with dev_tabs[4]:
            st.subheader("📄 تنزيل وإعادة رفع إكسيل الأطر")
            sample_df = pd.DataFrame({
                "الاسم الكامل": ["أحمد العبدلاوي", "فاطمة الزهراء"],
                "البريد الإلكتروني": ["ahmed@school.ma", "fatima@school.ma"],
                "رقم الهاتف": ["0611223344", "0655667788"],
                "الدور": ["teacher", "supervisor"],
                "الصفة الدقيقة": ["أستاذ الرياضيات", "الحارس العام للخارجية"],
                "كلمة السر": ["123456", "123456"]
            })
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                sample_df.to_excel(writer, index=False, sheet_name='الأطر')
            st.download_button("⬇️ تحميل قالب إكسيل استيراد الأطر جاهز", data=buffer.getvalue(), file_name="staff_import_template.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            
            st.divider()
            uploaded_staff_excel = st.file_uploader("رفع ملف إكسيل الأطر بعد ملئه:", type=['xlsx'], key="staff_uploader")
            if uploaded_staff_excel:
                try:
                    df_up_staff = pd.read_excel(uploaded_staff_excel)
                    if st.button("تأكيد تسجيل كافة الأطر المرفقة في الملف"):
                        c = conn.cursor()
                        count_s = 0
                        for _, r_s in df_up_staff.iterrows():
                            c.execute("INSERT OR IGNORE INTO users (username, password, full_name, role, custom_title, status, phone, email, must_change_password) VALUES (?, ?, ?, ?, ?, 'active', ?, ?, 1)",
                                      (str(r_s['البريد الإلكتروني']).strip(), str(r_s['كلمة السر']).strip(), str(r_s['الاسم الكامل']).strip(), str(r_s['الدور']).strip(), str(r_s['الصفة الدقيقة']).strip(), str(r_s['رقم الهاتف']).strip(), str(r_s['البريد الإلكتروني']).strip()))
                            count_s += 1
                        conn.commit()
                        st.success(f"🎉 تم تسجيل {count_s} إطار بنجاح!")
                except Exception as e:
                    st.error(f"خطأ في التحليل: {e}")

        with dev_tabs[5]:
            st.subheader("🔑 إمكانيات المطور: إدارة وتصفية الحسابات")
            all_users = pd.read_sql_query("SELECT id, username, full_name, role FROM users WHERE role != 'developer'", conn)
            if not all_users.empty:
                sel_u_id = st.selectbox("اختر الحساب للتعديل أو المسح:", all_users['id'].tolist(), format_func=lambda x: f"{all_users[all_users['id']==x]['full_name'].values[0]} ({all_users[all_users['id']==x]['username'].values[0]})")
                new_pass_dev = st.text_input("كلمة سر جديدة لهذا الحساب:")
                col_u1, col_u2 = st.columns(2)
                with col_u1:
                    if st.button("تحديث كلمة السر للحساب"):
                        c = conn.cursor()
                        c.execute("UPDATE users SET password = ? WHERE id = ?", (new_pass_dev, sel_u_id))
                        conn.commit()
                        st.success("تم التحديث بنجاح.")
                with col_u2:
                    if st.button("🗑️ مسح الحساب نهائياً", type="primary"):
                        c = conn.cursor()
                        c.execute("DELETE FROM users WHERE id = ?", (sel_u_id,))
                        conn.commit()
                        st.success("تم مسح الحساب بنجاح!")

        conn.close()

    # =========================================================
    # 2. ADMINISTRATION & SUPERVISOR ROLE (المديرون والحراس العامون)
    # =========================================================
    elif role in ['admin', 'supervisor']:
        st.markdown(f"""
            <div style="background: linear-gradient(135deg, #1e293b, #0f172a); padding: 1.5rem; border-radius: 12px; border: 1px solid #38bdf8; margin-bottom: 1.5rem;">
                <h2 style="color: #38bdf8; margin: 0;">🏛️ أهلاً بك في منصة الإدارة، <span style="color: #facc15;">{st.session_state.user['full_name']}</span> ({st.session_state.user['custom_title']})</h2>
                <p style="color: #cbd5e1; margin-top: 5px;">نسعد بجهودكم المستمرة في ضبط إيقاع المؤسسة ومواكبة تتبع الزمن المدرسي.</p>
            </div>
        """, unsafe_allow_html=True)

        admin_tabs = st.tabs([
            "🎫 تراخيص الدخول (Permits)", 
            "📊 الإحصائيات الشاملة والطباعة", 
            "🚨 تنبيهات عتبة الغياب", 
            "💬 مراسلات الأطر والرسائل الرسمية", 
            "📢 الإخبارات العامة", 
            "📄 تقارير الغياب المفصلة"
        ])
        conn = get_db_connection()
        
        with admin_tabs[0]:
            st.subheader("🎟️ إصدار ترخيص بالدخول لتلميذ (Permit de Rentrée)")
            cls_list = pd.read_sql_query("SELECT class_name FROM classes", conn)['class_name'].tolist()
            sel_p_cls = st.selectbox("اختر القسم:", cls_list if cls_list else [""])
            
            std_in_cls = pd.read_sql_query("SELECT id, student_number, full_name, massar_id FROM students WHERE class_name = ?", conn, params=(sel_p_cls,))
            if not std_in_cls.empty:
                sel_std_p = st.selectbox("اختر التلميذ(ة):", std_in_cls['id'].tolist(), format_func=lambda x: f"({std_in_cls[std_in_cls['id']==x]['student_number'].values[0]}) {std_in_cls[std_in_cls['id']==x]['full_name'].values[0]}")
                permit_reason = st.text_input("سبب الترخيص بالدخول (مثال: مبرر مقبول / إذن الإدارة):", value="مبرر مقبول")
                
                if st.button("إصدار ورقة الترخيص بالدخول وإرسالها فوراً للأستاذ", type="primary"):
                    c = conn.cursor()
                    c.execute("INSERT INTO entry_permits (student_id, issued_by, reason, timestamp) VALUES (?, ?, ?, ?)",
                              (sel_std_p, st.session_state.user['custom_title'], permit_reason, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    conn.commit()
                    st.success("🎉 تم إصدار الترخيص وتحديث تطبيق الأستاذ والتلميذ فوراً!")
                    
            st.divider()
            st.subheader("سجل التراخيص الصادرة اليوم")
            permits_today = pd.read_sql_query("SELECT p.timestamp as 'الوقت', s.full_name as 'التلميذ', s.class_name as 'القسم', p.issued_by as 'المصدر', p.reason as 'السبب' FROM entry_permits p JOIN students s ON p.student_id = s.id ORDER BY p.id DESC LIMIT 10", conn)
            st.dataframe(permits_today, use_container_width=True)

        with admin_tabs[1]:
            st.subheader("📊 إحصائيات الغياب ونسب الحضور العامة")
            tot_students = pd.read_sql_query("SELECT COUNT(*) as count FROM students", conn)['count'].values[0]
            tot_absence = pd.read_sql_query("SELECT SUM(total_absent_hours) as sum FROM students", conn)['sum'].values[0] or 0
            
            c1, c2, c3 = st.columns(3)
            c1.metric("إجمالي التلاميذ", f"{tot_students} تلميذ")
            c2.metric("مجموع ساعات الغياب المسجلة", f"{tot_absence} ساعة")
            c3.metric("نسبة الحضور العامة", f"{max(0, round(100 - (tot_absence/(tot_students*300 if tot_students else 1))*100, 2))}%")
            
            st.divider()
            st.subheader("طباعة تقرير المواظبة والغياب حسب القسم")
            if cls_list:
                sel_print_cls = st.selectbox("اختر القسم للطباعة:", cls_list, key="sel_print_cls")
                rep_cls_df = pd.read_sql_query("SELECT student_number as 'الرقم', massar_id as 'رقم مسار', full_name as 'الاسم الكامل', total_absent_hours as 'ساعات الغياب', attendance_points as 'نقاط المواظبة' FROM students WHERE class_name = ? ORDER BY student_number", conn, params=(sel_print_cls,))
                st.dataframe(rep_cls_df, use_container_width=True)
                st.download_button("🖨️ تحميل التقرير للطباعة (CSV)", data=rep_cls_df.to_csv(index=False).encode('utf-8'), file_name=f"report_{sel_print_cls}.csv", mime="text/csv")

        with admin_tabs[2]:
            st.subheader("🚨 التلاميذ المتجاوزون لعتبات الغياب (4 ساعات فأكثر)")
            absent_risk = pd.read_sql_query("SELECT id, student_number, massar_id, full_name, class_name, total_absent_hours FROM students WHERE total_absent_hours >= 4 ORDER BY total_absent_hours DESC", conn)
            st.dataframe(absent_risk, use_container_width=True)
            
            if not absent_risk.empty:
                st.divider()
                target_sid = st.selectbox("اختر التلميذ لإرسال تنبيه إداري رسمي ثابت:", absent_risk['id'].tolist(), format_func=lambda x: absent_risk[absent_risk['id']==x]['full_name'].values[0])
                notice_text = st.text_area("نص الإنذار / التنبيه الإداري:")
                if st.button("إرسال التنبيه الثابت"):
                    if notice_text:
                        c = conn.cursor()
                        c.execute("INSERT INTO student_disciplinary_records (student_id, issuer_title, notice_type, content, created_at) VALUES (?, ?, 'إنذار إداري رسمي', ?, ?)",
                                  (target_sid, st.session_state.user['custom_title'], notice_text, datetime.now().strftime("%Y-%m-%d %H:%M")))
                        conn.commit()
                        st.success("تم إرسال التنبيه الثابت بنجاح.")

        with admin_tabs[3]:
            st.subheader("💬 غرف الرسائل والإشعارات الرسمية بين الأطر (المديرون والحراس العامون)")
            msg_input = st.text_input("اكتب مراسلة إدارية بينية:")
            if st.button("إرسال المراسلة الرسمية"):
                if msg_input:
                    c = conn.cursor()
                    c.execute("INSERT INTO staff_chats (sender_name, sender_title, message, timestamp) VALUES (?, ?, ?, ?)",
                              (st.session_state.user['full_name'], st.session_state.user['custom_title'], msg_input, datetime.now().strftime("%Y-%m-%d %H:%M")))
                    conn.commit()
                    st.success("تم الإرسال.")
            
            chats = pd.read_sql_query("SELECT sender_name, sender_title, message, timestamp FROM staff_chats ORDER BY id DESC LIMIT 15", conn)
            for _, ch in chats.iterrows():
                st.markdown(f"📩 **{ch['sender_title']} ({ch['sender_name']})** - `<span class='highlight-yellow'>{ch['timestamp']}</span>`:\n\n{ch['message']}", unsafe_allow_html=True)

        with admin_tabs[4]:
            st.subheader("📢 نشر إخبار عاجل للأولياء والتلاميذ")
            title = st.text_input("عنوان الإخبار")
            msg = st.text_area("مضمون الإخبار")
            if st.button("نشر فوري عبر البوابة"):
                c = conn.cursor()
                c.execute("INSERT INTO flash_announcements (title, message, expiry_date, publisher, created_at) VALUES (?, ?, ?, ?, ?)",
                          (title, msg, str(date.today() + timedelta(days=5)), st.session_state.user['custom_title'], datetime.now().strftime("%Y-%m-%d")))
                conn.commit()
                st.success("تم النشر بنجاح.")

        with admin_tabs[5]:
            st.subheader("📄 تقارير الغياب المفصلة والمادة الأكثر تغيباً فيها")
            detailed_df = pd.read_sql_query("""
                SELECT s.full_name as 'اسم التلميذ', s.class_name as 'القسم', a.subject as 'المادة', a.session_time as 'توقيت الحصة', a.date as 'التاريخ', a.recorded_by as 'المسجل'
                FROM absence_records a JOIN students s ON a.student_id = s.id ORDER BY a.id DESC LIMIT 50
            """, conn)
            st.dataframe(detailed_df, use_container_width=True)

        conn.close()

    # =========================================================
    # 3. TEACHER ROLE (بوابة الأستاذ)
    # =========================================================
    elif role == 'teacher':
        st.markdown(f"""
            <div style="background: linear-gradient(135deg, #1e293b, #0f172a); padding: 1.5rem; border-radius: 12px; border: 1px solid #38bdf8; margin-bottom: 1.5rem;">
                <h2 style="color: #38bdf8; margin: 0;">👨‍🏫 مرحباً بك أستاذنا الفاضل، <span style="color: #facc15;">{st.session_state.user['full_name']}</span> ({st.session_state.user['custom_title']})</h2>
                <p style="color: #cbd5e1; margin-top: 5px;">بوابتك الرقمية لتسجيل المواظبة، تتبع السلوك، وإرسال التقارير بكل سهولة ويسر.</p>
            </div>
        """, unsafe_allow_html=True)
        
        with st.expander("💡 بوابة التنبيهات وإرشادات الاستخدام السريع (أضغط هنا للمساعدة)", expanded=False):
            st.markdown("""
                * **اختيار القسم والحصة:** قم بتحديد القسم الذي تدرسه حالياً من القائمة المنسدلة، ثم اختر الحصة المناسبة.
                * **تسجيل الغياب السريع:** ضع علامة ✅ بجانب اسم التلميذ الغائب فقط دون الحاجة لكتابة طويلة.
                * **الملاحظات الجاهزة:** يمكنك اختيار ملاحظة جاهزة من القائمة أو كتابة ملاحظة خاصة لتثبت فوراً في السجل التأديبي.
                * **التنبيه الفوري:** بمجرد الحفظ، سيتم إرسال إشعار فوري وتنبيه لحساب ولي الأمر والتلميذ بالغياب والتاريخ.
            """)

        conn = get_db_connection()

        t_classes_query = pd.read_sql_query("SELECT DISTINCT class_name FROM teacher_timetable WHERE teacher_username = ?", conn, params=(st.session_state.user['username'],))
        t_classes = t_classes_query['class_name'].tolist() if not t_classes_query.empty else pd.read_sql_query("SELECT class_name FROM classes", conn)['class_name'].tolist()
        
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            sel_cls = st.selectbox("اختر القسم أو المجموعة الحالية:", t_classes if t_classes else ["لم تُدرج أقسام بعد"])
        with col_t2:
            sess_num = st.selectbox("اختر الحصة الدراسية:", options=list(SESSIONS.keys()), format_func=lambda x: f"الحصة {x} ({SESSIONS[x]['time']})")
            
        st.divider()

        permits_in_cls = pd.read_sql_query("""
            SELECT s.full_name, p.reason, p.timestamp 
            FROM entry_permits p JOIN students s ON p.student_id = s.id 
            WHERE s.class_name = ? AND p.timestamp LIKE ?
        """, conn, params=(sel_cls, f"{date.today().strftime('%Y-%m-%d')}%"))
        
        if not permits_in_cls.empty:
            st.info("🎟️ **تلاميذ حصلوا على ترخيص دخول من الحراسة العامة لهذه الحصة:**")
            for _, pm in permits_in_cls.iterrows():
                st.markdown(f"✅ التلميذ(ة): **{pm['full_name']}** - السبب: {pm['reason']} ({pm['timestamp']})")

        st.subheader("📋 قائمة تلاميذ القسم لتسجيل الغياب والسلوك بسرعة:")
        std_df = pd.read_sql_query("SELECT id, student_number, full_name, total_absent_hours FROM students WHERE class_name = ? ORDER BY student_number", conn, params=(sel_cls,))

        if not std_df.empty:
            absent_ids = []
            notes_dict = {}

            st.write("ضع علامة ✅ أمام التلميذ الغائب في هذه الحصة:")
            for _, r in std_df.iterrows():
                c_chk, c_preset = st.columns([2, 2])
                with c_chk:
                    is_abs = st.checkbox(f"رقم ({r['student_number']}) - {r['full_name']} (غيابه السالف: {r['total_absent_hours']} س)", key=f"t_abs_{r['id']}")
                    if is_abs:
                        absent_ids.append(r['id'])
                with c_preset:
                    note_sel = st.selectbox(f"ملاحظة للتلميذ {r['student_number']}", [""] + PRESET_NOTES, key=f"t_note_{r['id']}")
                    if note_sel:
                        notes_dict[r['id']] = note_sel

            st.divider()
            custom_note_gen = st.text_input("أو اكتب ملاحظة سلوكية خاصة (تثبت فوراً في سجل التلميذ):")

            if st.button("حفظ وتأكيد تسجيل غياب الحصة اللحظي وإرسال الإشعار", type="primary"):
                c = conn.cursor()
                curr_subject = "المعلوماتية"
                
                for sid in absent_ids:
                    note_to_save = notes_dict.get(sid, custom_note_gen)
                    c.execute("""
                        INSERT INTO absence_records (student_id, class_name, date, session_number, session_time, recorded_by, subject, note)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (sid, sel_cls, str(date.today()), sess_num, SESSIONS[sess_num]['time'], st.session_state.user['custom_title'], curr_subject, note_to_save))
                    
                    c.execute("UPDATE students SET total_absent_hours = total_absent_hours + 1, attendance_points = MAX(0, attendance_points - 2) WHERE id = ?", (sid,))
                    
                    disc_msg = f"تنبيه غياب مؤكد في حصة {curr_subject} بتاريخ {str(date.today())} - توقيت: {SESSIONS[sess_num]['time']}. الملاحظة: {note_to_save or 'تغيب بدون إذن'}"
                    c.execute("""
                        INSERT INTO student_disciplinary_records (student_id, issuer_title, notice_type, content, created_at)
                        VALUES (?, ?, 'إشعار غياب وسلوك فوري', ?, ?)
                    """, (sid, st.session_state.user['custom_title'], disc_msg, datetime.now().strftime("%Y-%m-%d %H:%M")))
                
                conn.commit()
                st.success("🎉 تم بنجاح تسجيل الغياب وتحديث نقاط وسوابق التلاميذ وإرسال الإشعارات للولي!")
        else:
            st.warning("لا يوجد تلاميذ مسجلون في هذا القسم بعد.")

        st.divider()
        st.subheader("🖨️ طباعة إحصائيات الغياب الخاصة بمادتي لهذا القسم")
        if st.button("توليد تقرير غيابات الأستاذ"):
            rep_t_df = pd.read_sql_query("""
                SELECT s.full_name as 'التلميذ', a.date as 'التاريخ', a.session_time as 'الحصة', a.note as 'الملاحظة'
                FROM absence_records a JOIN students s ON a.student_id = s.id
                WHERE a.class_name = ? AND a.recorded_by = ?
            """, conn, params=(sel_cls, st.session_state.user['custom_title']))
            st.dataframe(rep_t_df, use_container_width=True)

        conn.close()

    # =========================================================
    # 4. PARENT & STUDENT ROLE (فضاء التلميذ والولي)
    # =========================================================
    elif role == 'parent':
        std = st.session_state.active_parent_student
        st.title(f"👁️ فضاء مراقبة المواظبة والنتائج: {std['full_name']}")
        
        if std['total_absent_hours'] == 0:
            st.markdown("""
                <div class="success-box">
                    🌟 تبارك الله! ابنكم/ابنتكم من التلاميذ المواظبين والمجتهدين في القسم. استمروا على هذا المستوى المتميز!
                </div>
            """, unsafe_allow_html=True)
        elif std['total_absent_hours'] >= 4:
            st.markdown(f"""
                <div class="alert-box">
                    🚨 تنبيه هام لولي الأمر: ابنكم/ابنتكم متغيب بكثرة (مجموع الساعات: {std['total_absent_hours']} ساعة). يرجى الاطلاع على التواريخ أسفله والاتصال بالإدارة للتحقق.
                </div>
            """, unsafe_allow_html=True)

        conn = get_db_connection()

        rank_df = pd.read_sql_query("""
            SELECT id, full_name, total_absent_hours,
                   RANK() OVER (ORDER BY total_absent_hours ASC, attendance_points DESC) as rank_pos
            FROM students WHERE class_name = ?
        """, conn, params=(std['class_name'],))
        
        my_rank = rank_df[rank_df['id'] == std['id']]['rank_pos'].values
        rank_val = my_rank[0] if len(my_rank) > 0 else 1

        c_p1, c_p2, c_p3 = st.columns(3)
        c_p1.metric("مجموع ساعات الغياب منذ بداية الموسم", f"{std['total_absent_hours']} ساعة")
        c_p2.metric("رصيد نقاط المواظبة", f"{std['attendance_points']} / 100")
        c_p3.metric("ترتيب التلميذ على المواظبة بالقسم", f"المرتبة {rank_val}")

        st.divider()
        st.subheader("📅 تفاصيل الساعات والحصص التي تغيب فيها التلميذ:")
        abs_history = pd.read_sql_query("""
            SELECT date as 'التاريخ', session_time as 'توقيت الحصة', subject as 'المادة', recorded_by as 'المستجوب/الأستاذ', note as 'الملاحظة'
            FROM absence_records WHERE student_id = ? ORDER BY id DESC
        """, conn, params=(std['id'],))
        
        if not abs_history.empty:
            st.dataframe(abs_history, use_container_width=True)
        else:
            st.success("🎉 لم يتم تسجيل أي حالة غياب باسمك، مواظبة ممتازة!")

        st.divider()
        st.subheader("🚨 الإشعارات والإنذارات الموجهة لولي الأمر حول التأخر والسلوكات:")
        notices = pd.read_sql_query("""
            SELECT issuer_title as 'المرسل', notice_type as 'نوع الإشعار', content as 'التفاصيل', created_at as 'التاريخ'
            FROM student_disciplinary_records WHERE student_id = ? ORDER BY id DESC
        """, conn, params=(std['id'],))
        
        if not notices.empty:
            st.warning("⚠️ ملاحظة هامة: هذه الإشعارات موثقة رسمياً من طرف الأستاذ أو الإدارة لإعلامكم بلحظة الغياب والسلوك.")
            st.dataframe(notices, use_container_width=True)
        else:
            st.success("سجلك نظيف تماماً وخالٍ من أي تنبيهات.")

        st.divider()
        st.info("🔒 ملاحظة: تغيير الرمز السري للتلميذ يتم حصرياً بحضور ولي الأمر شخصياً لدى الحارس العام للمؤسسة لطلب تغييرها.")

        conn.close()
