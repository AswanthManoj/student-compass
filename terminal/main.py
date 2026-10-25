# ---- STUDENT COMPASS ----
# Menu-driven program using SQLite connectivity
# Predicts board marks from test marks and suggests careers using a quiz

import sqlite3
from prettytable import PrettyTable

SUBJECTS = {
    "PCM": ["Physics", "Chemistry", "Mathematics", "English", "Computer Science"],
    "PCB": ["Physics", "Chemistry", "Biology", "English", "Physical Education"],
    "Commerce": ["Accountancy", "Business Studies", "Economics", "English", "Mathematics"],
    "Humanities": ["History", "Political Science", "Psychology", "English", "Economics"],
}

CAREERS = ["Computer Science & AI", "Engineering", "Medicine", "Psychology", "Research & Science",
           "Design & Architecture", "Media & Arts", "Law", "Business & Commerce"]

# Each option gives 1 point to the careers listed with it
QUIZ = [
    ["What do you enjoy doing in your free time?",
     ["Coding or fixing gadgets", ["Computer Science & AI", "Engineering"]],
     ["Helping someone who is unwell or upset", ["Medicine", "Psychology"]],
     ["Drawing, designing or making videos", ["Design & Architecture", "Media & Arts"]],
     ["Selling things or planning an event", ["Business & Commerce"]]],
    ["Which subjects do you like the most?",
     ["Maths and Physics", ["Engineering", "Computer Science & AI", "Research & Science"]],
     ["Biology and Chemistry", ["Medicine", "Research & Science"]],
     ["Accounts and Economics", ["Business & Commerce"]],
     ["English, History or Political Science", ["Law", "Media & Arts"]]],
    ["In a group project, what do you usually do?",
     ["Build or code the model", ["Engineering", "Computer Science & AI"]],
     ["Find the facts and check the data", ["Research & Science"]],
     ["Make the slides and the poster", ["Design & Architecture", "Media & Arts"]],
     ["Lead the team and present", ["Business & Commerce", "Law"]]],
    ["Where would you like to work one day?",
     ["A hospital or clinic", ["Medicine", "Psychology"]],
     ["A lab or research centre", ["Research & Science", "Medicine"]],
     ["An office, company or court", ["Business & Commerce", "Law"]],
     ["A studio or a tech company", ["Design & Architecture", "Computer Science & AI"]]],
    ["What would make a job feel worth it?",
     ["Helping people feel better", ["Medicine", "Psychology"]],
     ["Building things people use", ["Computer Science & AI", "Engineering"]],
     ["Making things fair for everyone", ["Law", "Psychology"]],
     ["Earning well and growing a business", ["Business & Commerce"]]],
]


# ---- Database Connection Function ----
def connect():
    con = sqlite3.connect("compass.db")
    return con


# ---- Create tables if they don't exist ----
def create_tables():
    con = connect()
    cur = con.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS students (student_id INTEGER PRIMARY KEY, name TEXT, stream TEXT, attendance REAL)")
    cur.execute("CREATE TABLE IF NOT EXISTS marks (student_id INTEGER, subject TEXT, ut1 REAL, half_yearly REAL, ut2 REAL, pre_board REAL)")
    cur.execute("CREATE TABLE IF NOT EXISTS careers (student_id INTEGER, career TEXT, score INTEGER)")
    con.commit()
    con.close()


# ---- Read a number between 0 and 100 ----
def read_percent(message):
    while True:
        try:
            value = float(input(message))
            if 0 <= value <= 100:
                return value
            print("Enter a value between 0 and 100.")
        except ValueError:
            print("Please enter a number.")


# ---- Find a student by ID ----
def find_student(student_id):
    con = connect()
    cur = con.cursor()
    cur.execute("SELECT * FROM students WHERE student_id = ?", (student_id,))
    row = cur.fetchone()
    con.close()
    return row


# ---- 1. Add Student ----
def add_student():
    name = input("Enter student name: ")
    print("Streams:", ", ".join(SUBJECTS))
    stream = input("Enter stream: ")
    if stream not in SUBJECTS:
        print("Stream not found. Type it exactly as shown.")
        return
    attendance = read_percent("Enter attendance (%): ")
    con = connect()
    cur = con.cursor()
    cur.execute("INSERT INTO students (name, stream, attendance) VALUES (?, ?, ?)", (name, stream, attendance))
    con.commit()
    print("Student added with ID", cur.lastrowid)
    con.close()


# ---- 2. Enter Marks ----
def enter_marks():
    student_id = int(input("Enter student ID: "))
    student = find_student(student_id)
    if student is None:
        print("Student ID not found. Add the student first using option 1.")
        return
    con = connect()
    cur = con.cursor()
    cur.execute("DELETE FROM marks WHERE student_id = ?", (student_id,))
    for subject in SUBJECTS[student[2]]:
        print("\n" + subject)
        ut1 = read_percent("  Unit Test 1: ")
        hy = read_percent("  Half-Yearly: ")
        ut2 = read_percent("  Unit Test 2: ")
        pb = read_percent("  Pre-Board: ")
        cur.execute("INSERT INTO marks VALUES (?, ?, ?, ?, ?, ?)", (student_id, subject, ut1, hy, ut2, pb))
    con.commit()
    con.close()
    print("Marks saved!")


# ---- 3. Show All Students ----
def show_students():
    con = connect()
    cur = con.cursor()
    cur.execute("SELECT * FROM students")
    rows = cur.fetchall()
    con.close()
    table = PrettyTable()
    table.field_names = ["Student ID", "Name", "Stream", "Attendance (%)"]
    for r in rows:
        table.add_row([r[0], r[1], r[2], r[3]])
    print(table)


# ---- Predict the board mark from the four tests ----
def predict(ut1, hy, ut2, pb):
    average = (ut1 + hy + ut2 + pb) / 4
    change = (pb - ut1) / 3          # marks gained or lost per test
    result = average + change
    if result > 100:
        result = 100
    if result < 0:
        result = 0
    return round(result, 1)


# ---- Convert a percentage to a CBSE grade ----
def grade(percent):
    if percent >= 91:
        return "A1"
    elif percent >= 81:
        return "A2"
    elif percent >= 71:
        return "B1"
    elif percent >= 61:
        return "B2"
    elif percent >= 51:
        return "C1"
    elif percent >= 41:
        return "C2"
    elif percent >= 33:
        return "D"
    else:
        return "E"


# ---- 4. Show Marks and Board Prediction ----
def show_report():
    student_id = int(input("Enter student ID: "))
    student = find_student(student_id)
    if student is None:
        print("Student ID not found.")
        return
    con = connect()
    cur = con.cursor()
    cur.execute("SELECT * FROM marks WHERE student_id = ?", (student_id,))
    rows = cur.fetchall()
    con.close()
    if len(rows) == 0:
        print("No marks found. Enter marks using option 2.")
        return

    table = PrettyTable()
    table.field_names = ["Subject", "UT 1", "Half-Yearly", "UT 2", "Pre-Board", "Predicted", "Grade", "Trend"]
    total = 0
    advice = []
    for r in rows:
        subject, ut1, hy, ut2, pb = r[1], r[2], r[3], r[4], r[5]
        predicted = predict(ut1, hy, ut2, pb)
        total = total + predicted
        if pb - ut1 >= 5:
            trend = "Improving"
        elif ut1 - pb >= 5:
            trend = "Falling"
            advice.append(subject + " has dropped from " + str(ut1) + " to " + str(pb) + ". Revise the recent chapters.")
        else:
            trend = "Steady"
        if predicted < 60:
            advice.append(subject + " is heading for " + str(predicted) + ". Practise past board papers daily.")
        table.add_row([subject, ut1, hy, ut2, pb, predicted, grade(predicted), trend])

    overall = round(total / len(rows), 1)
    attendance = student[3]
    if attendance < 75:
        advice.append("Attendance is " + str(attendance) + "%. CBSE needs at least 75% to sit the board exam.")

    print("\n*********** REPORT FOR", student[1].upper(), "***********")
    print(table)
    print("Predicted board percentage:", overall, "  Grade:", grade(overall))
    print("\nWHERE TO IMPROVE:")
    if len(advice) == 0:
        print("- No problems found. Keep it up!")
    for line in advice:
        print("-", line)


# ---- 5. Career Quiz ----
def career_quiz():
    student_id = int(input("Enter student ID: "))
    student = find_student(student_id)
    if student is None:
        print("Student ID not found.")
        return

    points = {}
    possible = {}
    for career in CAREERS:
        points[career] = 0
        possible[career] = 0

    for question in QUIZ:
        print("\n" + question[0])
        options = question[1:]
        for i in range(len(options)):
            print(" ", i + 1, ".", options[i][0])
            for career in options[i][1]:
                possible[career] = possible[career] + 1
        choice = 0
        while choice < 1 or choice > len(options):
            try:
                choice = int(input("Your answer (1-" + str(len(options)) + "): "))
                if choice < 1 or choice > len(options):
                    print("Choose a number from 1 to", len(options))
            except ValueError:
                print("Please enter a number.")
        for career in options[choice - 1][1]:
            points[career] = points[career] + 1

    con = connect()
    cur = con.cursor()
    cur.execute("DELETE FROM careers WHERE student_id = ?", (student_id,))
    for career in CAREERS:
        score = round(points[career] / possible[career] * 100)
        cur.execute("INSERT INTO careers VALUES (?, ?, ?)", (student_id, career, score))
    con.commit()
    con.close()
    print("\nQuiz done! Choose option 6 to see your career results.")


# ---- 6. Show Career Results ----
def show_careers():
    student_id = int(input("Enter student ID: "))
    con = connect()
    cur = con.cursor()
    cur.execute("SELECT career, score FROM careers WHERE student_id = ? ORDER BY score DESC", (student_id,))
    rows = cur.fetchall()
    con.close()
    if len(rows) == 0:
        print("No quiz results found. Take the quiz using option 5.")
        return
    table = PrettyTable()
    table.field_names = ["Rank", "Career", "Match (%)"]
    rank = 1
    for r in rows:
        table.add_row([rank, r[0], r[1]])
        rank = rank + 1
    print(table)
    print("Top suggestion:", rows[0][0])


# ---- 7. Delete Student ----
def delete_student():
    student_id = int(input("Enter student ID to delete: "))
    if find_student(student_id) is None:
        print("Student ID not found.")
        return
    con = connect()
    cur = con.cursor()
    cur.execute("DELETE FROM marks WHERE student_id = ?", (student_id,))
    cur.execute("DELETE FROM careers WHERE student_id = ?", (student_id,))
    cur.execute("DELETE FROM students WHERE student_id = ?", (student_id,))
    con.commit()
    con.close()
    print("Student deleted.")


# ---- MAIN MENU ----
def menudriven():
    create_tables()
    while True:
        print("\n*************** STUDENT COMPASS ***************")
        print("1. Add Student")
        print("2. Enter Marks")
        print("3. Show All Students")
        print("4. Show Marks and Board Prediction")
        print("5. Career Quiz")
        print("6. Show Career Results")
        print("7. Delete Student")
        print("8. Exit")
        try:
            choice = int(input("Enter your choice (1-8): "))
            if choice == 1:
                add_student()
            elif choice == 2:
                enter_marks()
            elif choice == 3:
                show_students()
            elif choice == 4:
                show_report()
            elif choice == 5:
                career_quiz()
            elif choice == 6:
                show_careers()
            elif choice == 7:
                delete_student()
            elif choice == 8:
                print("Thank you! Program ended.")
                break
            else:
                print("Invalid choice. Try again.")
        except ValueError:
            print("Please enter a number.")
        except sqlite3.Error as e:
            print("Database error:", e)


# ---- Run Program ----
menudriven()
