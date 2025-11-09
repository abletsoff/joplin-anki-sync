#!/home/andrew/Documents/scripts/joplin-anki-sync/venv/bin/python3

import requests
import json
import re
import hashlib
import os
import syslog

PYTHONHASHSEED=None

anki_origin="http://localhost:8765/"
joplin_origin="http://localhost:41184/"

token=""
folders={}
excluded_headers=()
excluded_notes=()
created=[]
updated=[]
deleted=[]

def config_parser():
    global token
    global folders
    global excluded_headers
    global excluded_notes
    global excluded_bold_blocks
    
    # Joplin web clipper authorization token parsing
    token_json=""
    paths=(f'{os.getenv("HOME")}/.config/joplin-desktop/joplin-anki-sync/token.json',
            f'{os.getenv("PWD")}/token.json')

    if (os.path.isfile(paths[0]) or os.path.isfile(paths[1])):
        if (os.path.isfile(paths[0])):
            path=paths[0]
        else:
            path=paths[1]
        with open(path) as config_file:
            try:
                token_json=json.load(config_file)
            except json.decoder.JSONDecodeError as error:
                print(f"[Error] JSON decoder error: {error}. Please check '{path}' syntax.")
                exit()
    else:
        print(f"[Error] At least one of the following files does not exist: '{paths}'."
                "Please read the manual :)")
        exit()

    token=token_json["token"]

    # Configuration parsing
    config_json=""
    paths=(f'{os.getenv("HOME")}/.config/joplin-desktop/joplin-anki-sync/config.json',
            f'{os.getenv("PWD")}/config.json')

    if (os.path.isfile(paths[0]) or os.path.isfile(paths[1])):
        if (os.path.isfile(paths[0])):
            path=paths[0]
        else:
            path=paths[1]
        with open(path) as config_file:
            try:
                config_json=json.load(config_file)
            except json.decoder.JSONDecodeError as error:
                print(f"[Error] JSON decoder error: {error}\nPlease check '{path}' syntax.")
                exit()
    else:
        print(f"[Error] At least one of the following files does not exist: '{paths}'.")
        exit()
        
    try:
        response = requests.get(f'{joplin_origin}folders?token={token}')
        response_json = json.loads(response.text)
    except requests.exceptions.ConnectionError:
        msg=f"Cannot connect to Joplin web clipper service ({joplin_origin})"
        print(msg)
        syslog.syslog(msg)
        exit()
    
    for joplin_folder in response_json["items"]:
        for config_folder in config_json["folders"]:
            if joplin_folder["title"] == config_folder:
                folders[f"{config_folder}"] = joplin_folder["id"]
                break
    excluded_headers = tuple(config_json["exclude_headers"])
    excluded_notes = tuple(config_json["exclude_notes"])
    excluded_bold_blocks = tuple(config_json["exclude_bold_block"])
    
    # At this moment, version check is used only for Error handling
    try:
        anki_json = {"action": "version","version": 6}
        response = requests.post(anki_origin, json=anki_json)
    except requests.exceptions.ConnectionError:
        msg=f"Cannot connect to Ankiconnect add-on ({anki_origin})"
        print(msg)
        syslog.syslog(msg)
        exit()

def joplin_note_parser(note_name, note_id):
    header_re=re.compile(r'^# .*', re.MULTILINE)
    attachment_re=re.compile(r']\(:/[a-f0-9]{32}\)', re.MULTILINE)
    response = requests.get(f'{joplin_origin}/notes/{note_id}?token={token}&fields=body')
    response_json = json.loads(response.text)
    markdown = response_json['body']
    headers = re.findall(header_re, markdown)
    headers_hash={}

    # Removing code coments from headers
    check=False
    comment_headers=[]
    for line in markdown.split('\n'):
            if re.search(r'^```', line):
                check = not check
            if check == True and re.search(r'^# .*', line):
                comment_headers.append(line)
    headers=list(set(headers) - set(comment_headers))

    for header in headers:
        if header.rstrip().startswith(excluded_headers):
            continue
        if "==" in header:
            continue
        write_segment=None # Is used to decide where is active content of specific H1 header
        excl_bold_block=False # Bold block to exclude from active segemnt
        content=''
        subheaders=[]
        for line in markdown.split('\n'):
            if re.search(header_re, line):
                if line not in comment_headers:
                    write_segment=None
            if write_segment != None: # Processing active content
                for exclude in excluded_bold_blocks:
                    if line == exclude:
                        excl_bold_block=True
                if excl_bold_block == False and not re.search(attachment_re, line):
                    content+=line
                if line == '' and excl_bold_block == True:
                    excl_bold_block=False
                if re.search(r'^##+', line):
                    subheaders.append(re.sub(r'^##+ ', '', line))
                if re.search(r'^\*\*.*\*\*$', line):
                    if line != "**Resources**":
                        subheaders.append(re.sub(r'\*\*', '+', line))
            if re.search(rf'^{header} *$', line):
                write_segment=header
        title = f"{note_name}  / {header.replace('# ', '')} {str(subheaders)}" 
        content_hash = hashlib.md5(content.replace(' ', '').encode()).hexdigest()
        headers_hash[title] = content_hash
    return headers_hash

def joplin_folder_parser (folder_id):
    response = requests.get(f'{joplin_origin}/folders/{folder_id}/notes?token={token}')
    response_json = json.loads(response.content)
    notes={}
    for note in response_json['items']:
        note_title = note['title']
        notes[note_title] = note['id']
    return notes
 
def anki_deck_parser(deck):
    anki_json = {"action": "findNotes","version": 6,"params": {"query": f"deck:{deck}"}}
    response = requests.post(anki_origin, json=anki_json)
    cards_id = json.loads(response.text)['result']
    cards = {}
    for card_id in cards_id:
        anki_json = {"action": "notesInfo","version": 6,"params": {"notes": [card_id]}}
        response = requests.post(anki_origin, json=anki_json)
        note_json = json.loads(response.text) 
        front = note_json['result'][0]['fields']['Front']['value']
        back = note_json['result'][0]['fields']['Back']['value']
        cards[card_id]=[front,back]
    return cards


def anki_add_card(deck, front, back, cards):
    anki_json= {
    "action": "addNote","version": 6,"params": {
        "note": {
            "deckName": deck, "modelName": "Basic","fields": {
                "Front": front, "Back": back
                }
            }
        }
    }
    for card_id, card_info in cards.items():
        if card_info[0] == front:
            if card_info[1] != back:
                anki_json_d={"action": "deleteNotes","version": 6,"params": {"notes": [card_id]}}
                response = requests.post(anki_origin, json=anki_json_d)
                response = requests.post(anki_origin, json=anki_json)
                updated.append(front)
            return
    response = requests.post(anki_origin, json=anki_json)
    created.append(front)

def anki_del_card(deck, titles, cards):
    exist=False
    for card_id, card_info in cards.items():
        for title in titles:
            if card_info[0] == title:
                exist=True
                break
        if not exist:
            anki_json = {"action": "notesInfo","version": 6,"params": {"notes": [card_id]}}
            response = requests.post(anki_origin, json=anki_json)
            note_json = json.loads(response.content) 
            front = note_json['result'][0]['fields']['Front']['value']
            deleted.append(front)
            anki_json_d={"action": "deleteNotes","version": 6,"params": {"notes": [card_id]}}
            response = requests.post(anki_origin, json=anki_json_d)
        exist=False

def statistic():
    print(f"Created cards: {len(created)}")
    for card in created:
        print(" -", card)
    print(f"Updated cards: {len(updated)}")
    for card in updated:
        print(" -", card)
    print(f"Deleted cards: {len(deleted)}")
    for card in deleted:
        print(" -", card)
    syslog.syslog(f"Created: {len(created)}, Updated: {len(updated)}, Deleted: {len(deleted)}")

config_parser()

for f_name,f_id in folders.items():
    cards = anki_deck_parser(f_name)
    notes = joplin_folder_parser(f_id)
    sum_titles=[]
    for n_name, n_id in notes.items():
        if n_name.startswith(excluded_notes):
            continue
        titles_hash = joplin_note_parser(n_name, n_id)
        for title, t_hash in titles_hash.items():
            anki_add_card(f_name, title, t_hash, cards)
            sum_titles.append(title)
    anki_del_card(f_name, sum_titles, cards)

statistic()
