# Factory bot profile

`avatar.svg` is the source (Pylyp from `characters/pylyp.svg` on a honeycomb, with a bee);
`avatar.jpg` is the 640x640 render set as the bot's profile photo via the Bot API
(`setMyProfilePhoto`). Re-render with headless Chrome:

```zsh
google-chrome --headless=new --hide-scrollbars --window-size=640,640 \
  --screenshot=avatar.png "file://$PWD/deploy/bot/avatar.svg"
```
