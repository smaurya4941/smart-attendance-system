import os
from datetime import datetime
import streamlit as st 
import sqlite3
import qrcode
import numpy as np
import face_recognition
from pyzbar.pyzbar import decode
import cv2


#buildinf=g setup files for qrcode and face encoding
os.makedirs("qrcodes",exist_ok=True)
os.makedirs("encodings",exist_ok=True)


#creating database
def init_db():
    student_db=sqlite3.connect("students.db")
    queries=student_db.cursor()

    # create a table to store students
    queries.execute(
        '''
            CREATE TABLE IF NOT EXISTS students(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            roll TEXT UNIQUE NOT NULL,
            class TEXT NOT NULL
            )
    '''
    )


    #creating attendance table
    queries.execute('''
            CREATE TABLE IF NOT EXISTS attendance(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER,
                date TEXT,
                time TEXT,
                method TEXT,
                status TEXT NOT NULL,
                FOREIGN KEY(student_id) REFERENCES students(id)
            )
            '''    
    )

    student_db.commit()
    student_db.close()


# function to add student + qrcode  +face recognition encodings
def add_student(name,roll,class_name,img_file):
    student_db=sqlite3.connect("students.db")
    queries=student_db.cursor()

    try:
        queries.execute(
            "Insert into students (name,roll,class) VALUES (?,?,?)",(name,roll,class_name)
        )
        student_db.commit()

        #now after the adding of students details let's generatre QRCODE based on the roll no.(unique)
        qr=qrcode.make(roll) #generating qrcode
        qr.save(f"qrcodes/{roll}.png")  #saving qrcode as png format for  each regisyred student in qrcodes folder

        # FACE ENCODINGS
        if img_file is not None:
            #directly image cannot be undrerstand by poencv so first conver to bytearray then as array
            file_bytes=np.asarray(bytearray(img_file.read()),dtype=np.uint8) 
            img=cv2.imdecode(file_bytes,1)
            rgb_img=cv2.cvtColor(img,cv2.COLOR_BGR2RGB)  #convertng img to RGB format
            encodings=face_recognition.face_encodings(rgb_img)  # generating encoding for image

            if encodings:
                np.save(f"encodings/{roll}.npy",encodings[0])
                st.success("Face encoding is saved")
            else:
                st.warning("Face is not detedcted in uploaded image")


        st.success(f" student {name} addedd successfully! with qrcode and face encodings")
    except sqlite3.IntegrityError:
        st.error("Roll number already exists")


    student_db.close()


#fetch students
def fetch_student():
    student_db=sqlite3.connect('students.db')
    queries=student_db.cursor()

    queries.execute(
        "select * from students"
    )
    rows=queries.fetchall()
    student_db.close()
    return rows

# View Attendance
def fetch_attendance():
        db = sqlite3.connect("students.db")  # use same DB
        cur = db.cursor()
        cur.execute("""
            SELECT s.name, s.roll, s.class, a.date, a.time, a.method, a.status
            FROM attendance a
            JOIN students s ON a.student_id = s.id
            ORDER BY a.date DESC, a.time DESC
        """)
        rows = cur.fetchall()
        db.close()
        return rows




def mark_attendance(roll,method):
    db = sqlite3.connect("students.db")
    cur = db.cursor()

    # get student_id from roll
    cur.execute("SELECT id FROM students WHERE roll=?", (roll,))
    student = cur.fetchone()
    if not student:
        db.close()
        return f"Student with roll {roll} not found!"

    student_id = student[0]

    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%H:%M:%S")

    # avoid duplicate for same day
    cur.execute("SELECT * FROM attendance WHERE student_id=? AND date=?", (student_id, today))
    existing = cur.fetchone()

    if not existing:
        cur.execute(
            "INSERT INTO attendance (student_id, date, time, method, status) VALUES (?, ?, ?, ?, ?)",
            (student_id, today, now, method, "Present")
        )
        db.commit()
        status = f"Attendance marked for roll {roll} via {method}"
    else:
        status = f"Attendance already marked today"

    db.close()
    return status


#Setting up QR Scanner with opencv and pyzbar
def scan_qr():
    cap=cv2.VideoCapture(0)
    qr_data=None

    frame_placeholder=st.empty()
    while True:
        ret,frame=cap.read()

        if not ret:
            st.warning("could not read frame")
            break

        #copy pasted code
        for qr in decode(frame):
            qr_data = qr.data.decode("utf-8")
            # Draw rectangle
            pts = qr.polygon
            pts = [(pt.x, pt.y) for pt in pts]
            pts = cv2.convexHull(np.array(pts, dtype=np.int32))
            cv2.polylines(frame, [pts], True, (0, 255, 0), 2)
            cv2.putText(frame, qr_data, (qr.rect.left, qr.rect.top - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 0, 0), 2)
            
            
        
    
        # cv2.imshow("QR Scanner - Press Q to exit", frame)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_placeholder.image(frame_rgb,channels="RGB")

        if qr_data:
            cap.release()
            return qr_data

        # if cv2.waitKey(1) & 0xFF == ord("q"):
        #     break

    cap.release()
    return None



#QR Attendance page
def qr_attendance_page():
    st.title("QR Attendance System")

    if st.button("Scan QR"):
        st.info("Scanning...Hold QR in front of camera")

        qr_data=scan_qr()

        if qr_data: #if QR is scanned
            #checking student exist in db
            attendance_db=sqlite3.connect("students.db")
            att_queries=attendance_db.cursor()

            att_queries.execute("SELECT * from students where roll=?",(qr_data,))
            student=att_queries.fetchone()
            attendance_db.close()

            if student:
                status=mark_attendance(qr_data,"QR") #here qr_data is roll number
                st.success(status)
            else:
                st.error("Student not found in database")

        else:
            st.warning("No QR is detected")        
                



#*********************************FACE BASED  ATTENDANCE

#LOading all the encodings 
# def load_encoding():
#     encodings={}
#     if not encodings:
#         st.error("No face encodings found! Please register a student first.")


#     for encoding in os.listdir("encodings"):
#         if encoding.endswith(".npy"):
#             roll=encoding.replace(".npy","")
#             encodings[roll]=np.load(os.path.join("encodings",encoding))  
            
#     # print(encodings) #Example: { "101": [128-dim encoding],
#     return encodings


def load_encoding():
    encodings = {}
    files = os.listdir("encodings")
    if not files:
        st.error("No face encodings found! Please register a student first.")
        return encodings

    for encoding in files:
        if encoding.endswith(".npy"):
            roll = encoding.replace(".npy", "")
            encodings[roll] = np.load(os.path.join("encodings", encoding))
    return encodings


def scan_face():
    known_encodings=load_encoding()  #it store the {roll:128-dim encoding } for all the registered students
    if not known_encodings:
        return None

    cap=cv2.VideoCapture(0)
    st.info("Scanning... Look into the camera")

    # Create a placeholder for live video in Streamlit
    frame_placeholder = st.empty()
    while True:
        ret,frame=cap.read()
        if not  ret:
            break
        
        rgb_img=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)

        #Detecting face locations using face recognition library anf functions
        face_locations=face_recognition.face_locations(rgb_img)
        face_encodings=face_recognition.face_encodings(rgb_img,face_locations) #isme webcam se liya gya frame ka encoding store hoga


        #ab face_encodings(via webcam) aur known_encodings(already stored ) ko compare karenge
        for (top, right, bottom, left), face_encoding in zip(face_locations,face_encodings):
            for roll,known_encoding in known_encodings.items():
                matches=face_recognition.compare_faces([known_encoding],face_encoding)  #comparing both encodings 
                if matches[0]:
                    cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                    cv2.putText(frame, roll, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 0, 0), 2)
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    frame_placeholder.image(frame_rgb, channels="RGB")
                    cap.release()
                    # cv2.destroyAllWindows()
                    return roll
                
        # cv2.imshow("Scanning.. presss Q to exit",frame)
        # Show live feed even if no match yet
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_placeholder.image(frame_rgb, channels="RGB")

        # if cv2.waitKey(1) & 0xff==ord('q'):
        #     break

    cap.release()
    # cv2.destroyAllWindows()
    return None




#marking attendance with face recognition
def face_attendance_page():
    st.title("Face Attendance System")

    if st.button("Scan Face"):
        roll = scan_face()
        if roll:
            status = mark_attendance(roll,"Face")   # mark directly
            st.success(status)
        else:
            st.warning("No face recognized")
