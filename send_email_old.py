import smtplib
from email.message import EmailMessage
from os.path import basename
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText
from secrets_parameters import calendar_manager_email, calendar_manager_password
#from email import Encoders
#from email import MIMEMultipart
from email import MIMEBase

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
    
    part = MIMEBase('application', 'octet-stream')
    part.set_payload(open('debug.log', 'rb').read())
    #Encoders.encode_base64(part)
    part.add_header(
            'Content-Disposition',
            'attachment; filename={}'.format(os.path.basename('debug.log'))
    )
    msg.attach(part)


    # send email
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(email_address, email_password)
        logger.info(smtp.send_message(msg))
