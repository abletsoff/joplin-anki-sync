#!/usr/bin/python3

import requests
import json
import re
import hashlib

PYTHONHASHSEED=None

anki_origin="http://localhost:8765/"
joplin_origin="http://localhost:41184/"
token="b34e8b824fc490fd9184d50535039b565a44d27cbb63f94ae85630bb8c8ea5ca9184d97a1a766ae173164c5f43" \
	  "cf03a5fb6f58107d3d490a3c362f19a364e394"

folders = {
        "TCP/IP":"46df78fe4ae94e21b9221d887633025f",
        "AppSec":"cbf1aecc6b5a4161ae2f36862e1c113d",
        "System":"7a6b9db94e5f4d3a98005ece95927ea8",
        "Programming":"09f327180873452da30d3603a3e3e13b"
}

# folders = {
#        "Programming":"09f327180873452da30d3603a3e3e13b"
# }

excluded_headers=("# ToDo", "# Resources", "# Knowledgebase", "# CLI", "# Projects",
                  "# Check list", "# Setup", "# Recipes" "# Cheat sheet")
excluded_notes=("Helpdesk ", "Projects ", "Keyboard cowboy")

created=[]
updated=[]
deleted=[]

header_re=re.compile(r'^# .*', re.MULTILINE)

def joplin_note_parser(note_name, note_id):
    response = requests.get(f'{joplin_origin}/notes/{note_id}?token={token}&fields=body')
    response_json = json.loads(response.text)
    markdown = response_json['body']
    headers = re.findall(header_re, markdown)
    headers_hash={}
    for header in headers:
        if header.rstrip().startswith(excluded_headers):
            continue
        if "==" in header:
            continue
        var=None
        content=''
        subheaders=[]
        for line in markdown.split('\n'):
            if re.search(header_re, line):
                var=None
            if var != None:
                content+=line
                if re.search(r'^##+', line):
                    subheaders.append(re.sub(r'^##+ ', '', line))
            if re.search(rf'{header} *$', line):
                var=header
        title = f"{note_name}  / {header.replace('# ', '')} {str(subheaders)}" 
        content_hash = hashlib.md5(content.replace(' ', '').encode()).hexdigest()
        headers_hash[title] = content_hash
    return headers_hash

def joplin_folder_parser (folder_id):
    response = requests.get(f'{joplin_origin}/folders/{folder_id}/notes?token={token}')
    response_json = json.loads(response.text)
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
            note_json = json.loads(response.text) 
            front = note_json['result'][0]['fields']['Front']['value']
            deleted.append(front)
            anki_json_d={"action": "deleteNotes","version": 6,"params": {"notes": [card_id]}}
            response = requests.post(anki_origin, json=anki_json_d)
        exist=False

def statistic():
    print(f"Created cards: {len(created)}")
    for card in created:
        print("\t", card)
    print(f"Updated cards: {len(updated)}")
    for card in updated:
        print("\t", card)
    print(f"Deleted cards: {len(deleted)}")
    for card in deleted:
        print("\t", card)

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
