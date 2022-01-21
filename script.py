# Included Python modules
import requests
import smtplib
from email import message
import datetime
import os

# Modules from pip
import libversion
import jira
from dotenv import load_dotenv

###############################################################################

load_dotenv()

# Misc

date = datetime.datetime.today().strftime('%Y-%m-%d')

# SMTP Setup and Template

smtp_server = os.getenv('SMTP_SERVER')
smtp_port = os.getenv('SMTP_PORT')

sender = os.getenv('SENDER')
destination = os.getenv('DESTINATION')

smtp_username = os.getenv('SMTP_USERNAME')
smtp_password = os.getenv('SMTP_PASSWORD')

email_subtype = "plain"

email_subject = "yiffOS package updates for " + date

email_packages_that_need_updates = ""
email_packages_that_have_jira_issues = ""
email_packages_with_issues = ""

# Jira Setup

jira = jira.JIRA("https://yiffos.atlassian.net/", basic_auth=(os.getenv("JIRA_EMAIL"), os.getenv("JIRA_TOKEN")))

# API Setup

toolchain = "knot"

api_endpoint = "https://repology.org/api/v1/"
complete_query = api_endpoint + "projects/?search=&maintainer=&category=&inrepo=yiffos_knot&notinrepo=&repos=&families=&repos_newest=&families_newest=&outdated=on"

########################################################################################################################

complete_response = requests.get(complete_query).json()
complete_keys = list(complete_response.keys())

for i in range(len(complete_keys)):
    package_name = "";
    yiffos_version = "";
    newest_version = "";
    update_needed = 0;
    legacy_version = False;

    project_response = requests.get(api_endpoint + "project/" + complete_keys[i]).json()
    
    for x in project_response:
        if x["repo"] == "yiffos_" + toolchain:
            package_name = x["srcname"]
            yiffos_version = x["version"]

            if x["status"] == "legacy":
                legacy_version = True

        elif x["status"] == "newest":
            newest_version = x["version"]
            
    if legacy_version:
        continue

    if newest_version != "":
        update_needed = libversion.version_compare2(newest_version, yiffos_version)

    print(package_name)
    print("yiffOS version: " + yiffos_version)
    print("Newer version: " + newest_version)

    match update_needed:
        case -1:
            email_packages_with_issues += package_name + ": v" + yiffos_version + " (libversion reports that it's newer than upstream, upstream version: " + newest_version + ")\n"
            print("yiffOS package is newer?")
        case 0:
            email_packages_with_issues += package_name + ": v" + yiffos_version + " (libversion reports that it's up to date, upstream version: " + newest_version + ")\n"
            print("No update needed.")
        case 1:  
            print("Update needed!")
            
            if jira.search_issues("project = PAC AND text ~ \"" + package_name + " " + newest_version + "\"", maxResults=1):
                email_packages_that_have_jira_issues += package_name + ": v" + yiffos_version + " --> v" + newest_version + "\n"
                print("Issue already exists.")
            else:
                jira.create_issue(project="PAC", summary="Update " + package_name + " to v" + newest_version, description="The package " + package_name + " is outdated. Please update it to version " + newest_version + ".", issuetype="Improvement")
                email_packages_that_need_updates += package_name + ": v" + yiffos_version + " --> v" + newest_version + "\n"
                print("Issue created.")


########################################################################################################################

print("Sending email...")

if email_packages_that_need_updates == "":
    email_packages_that_need_updates = "None!"

if email_packages_that_have_jira_issues == "":
    email_packages_that_have_jira_issues = "None!"

if email_packages_with_issues == "":
    email_packages_with_issues = "None!"

email_content = """\
This is the daily yiffOS package update report for {}

-------------------------------------------------------

New packages that need updating:
{}

Packages that still need updating:
{}

Packages with issues:
{}
""".format(date, email_packages_that_need_updates, email_packages_that_have_jira_issues, email_packages_with_issues)

try:
    msg = message.EmailMessage()
    msg.set_content(email_content)
    msg["Subject"] = email_subject
    msg["From"] = sender

    conn = smtplib.SMTP(smtp_server, smtp_port)
    conn.set_debuglevel(False)
    conn.ehlo()
    conn.starttls()
    conn.login(smtp_username, smtp_password)

    try:
        conn.sendmail(sender, destination, msg.as_string())
    finally:
        conn.quit()

except smtplib.SMTPException as e:
    print("Error: unable to send email")
    print(e)