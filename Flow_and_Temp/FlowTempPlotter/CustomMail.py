from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
from datetime import datetime


def send_mail(subject, content):
    try:
        # 파일 읽기
        with open('sender.txt', 'r') as f:
            lines = f.readlines()

        # 이메일 정보 설정
        for line in lines:
            if 'SMTP_SERVER' in line:
                SMTP_SERVER = line.split(',')[1].strip()
            elif 'SMTP_PORT' in line:
                SMTP_PORT = int(line.split(',')[1].strip())  # 포트는 정수로 변환
            elif 'SMTP_USER' in line:
                SMTP_USER = line.split(',')[1].strip()
            elif 'SMTP_PASSWORD' in line:
                SMTP_PASSWORD = line.split(',')[1].strip()

        print('SMTP_SERVER :', SMTP_SERVER)
        print('SMTP_PORT :', SMTP_PORT)
        print('SMTP_USER :', SMTP_USER)
        print('SMTP_PASSWORD :', SMTP_PASSWORD)

        # 보내는 이 정보
        SENDER = SMTP_USER

        # 받는 이 주소
        with open('recipent.txt', 'r') as f:
            RECIPIENT = f.readlines()
    except:
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open('maillog.txt', 'a') as file:
            # 한 줄의 로그 작성
            log_message = f'[{current_time}] 이메일 발신자/수신자 목록을 불러오는 데에 실패했습니다.\n'
            file.write(log_message)

    try:
        # 이메일 제목  = 현재 날짜 정보
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d %H:%M:%S")
        SUBJECT = f"{date_str} Plant is disconnected."

        # 이메일 생성
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = SENDER
        msg['To'] = ','.join(RECIPIENT)
        msg.attach(MIMEText(content))
    except:
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open('log.txt', 'a') as file:
            # 한 줄의 로그 작성
            log_message = f'[{current_time}] 이메일 객체를 생성하는 데에 실패했습니다.\n'
            file.write(log_message)

    try:
        # SMTP 서버 연결 및 이메일 전송
        smtp_server = smtplib.SMTP_SSL(host=SMTP_SERVER, port=SMTP_PORT)
        smtp_server.login(SMTP_USER, SMTP_PASSWORD)
        for reciever in RECIPIENT:
            smtp_server.sendmail(SENDER, reciever, msg.as_string())
        smtp_server.quit()
    except:
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open('log.txt', 'a') as file:
            # 한 줄의 로그 작성
            log_message = f'[{current_time}] 이메일을 보내는 도중 오류가 발생했습니다.\n'
            file.write(log_message)