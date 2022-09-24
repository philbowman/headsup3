import smtplib
from email.message import EmailMessage
from secrets_parameters import calendar_manager_email, calendar_manager_password

# set your email and password
# please use App Password
email_address = calendar_manager_email
email_password = calendar_manager_password
def send_email(subject, message):
    # create email
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = email_address
    msg['To'] = "pbowman@acsamman.edu.jo"
    msg.set_content(message)

    # send email
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(email_address, email_password)
        print(smtp.send_message(msg))