# Smartproctor
This is our project  SMARTPROCTOR  it is a online examination monitoring system.


Feature of smartproctor are

1️.Exam Status Logic
Purpose:
The Exam Status Logic controls the current state of an examination and decides whether students can access the exam or not
ex- Active,completed

2.Timer Logic
Purpose:
The Timer Logic controls the duration of the online exam and ensures automatic submission after time completion and during tab switching

3.Question Ordering Logic
Purpose:
This logic controls how questions are displayed to students during the examination.
like sequential order,random order, subjectwise

4️.One Attempt for One Roll Number Logic
Purpose:
This logic ensures that one student can attempt the exam only once using a unique roll number.

if  roll_number EXISTS in exam_attempts
   Denyy Access
ELSE
   Allow
