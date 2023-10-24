# joplin-anki-sync
Automated management of Anki cards based on Joplin notes for effective spaced repetition learning. 

# Requirements
- Joplin Web clipper service
- Anki AnkiConnect add-on

# Configuration
- Clone `https://github.com/abletsoff/joplin-anki-sync`
- Create and copy Joplin Web Clipper authorization token

![clipper](https://github.com/abletsoff/joplin-anki-sync/blob/main/images/clipper.png?raw=true)
- Create `token.json` file in the `joplin-anki-sync` directory with the following content:
``` json
{
        "token":"paste_your_authorization_token_here"
}
```
# Demo
## Script execution
![terminal](https://github.com/abletsoff/joplin-anki-sync/blob/main/images/terminal.png?raw=true)

## Anki card browse
![anki](https://github.com/abletsoff/joplin-anki-sync/blob/main/images/anki.png?raw=true)

## Joplin note
![joplin](https://github.com/abletsoff/joplin-anki-sync/blob/main/images/joplin.png?raw=true)
