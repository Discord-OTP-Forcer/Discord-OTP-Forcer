<h1 align="center">Troubleshooting</h1>

<p align="center">
<b>This part of the wiki should hopefully help you when something isn't working right.</b> The first thing to do before filing an issue is<br>1. check here for any issues you might face, <br>2. search the web for the error and try to solve it yourself.<br> If that doesn't work for you, feel free to file an issue with the details.

You might also want to check out these pages for fixes: 
- https://github.com/Discord-OTP-Forcer/Discord-OTP-Forcer/discussions/categories/tips-tricks-hacks
- https://codeberg.org/Discord-OTP-Forcer/Discord-OTP-Forcer/wiki/Useful-hacks
</p>

---

| Issue | Possible solution |
|     :---:      |     :---:     |
| `'pip' is not recognized as an internal or external command` | Make sure that you included pip with your Python installation. If you have and it's still not working, try running pip like this: `python.exe -m pip [command]`    |
| `The script is installed in directory, which is not PATH` | [https://superuser.com/questions/1372793/the-script-is-installed-in-directory-which-is-not-path](https://superuser.com/questions/1372793/the-script-is-installed-in-directory-which-is-not-path)

## Error when running the program in the temp directory
Extract the files from the .zip file which you downloaded. This program cannot run from a .zip file

## My config file isn't working!
Check if your config file is incorrectly formatted or you filled in a wrong option. If you did that and it's still not working, [file an issue](https://codeberg.org/Discord-OTP-Forcer/Discord-OTP-Forcer/issues/new?template=.github%2fISSUE_TEMPLATE%2fbug.yml) with the details. Remember to redact all personal details when reporting.

## In `programMode: Reset`, the browser is frozen/not moving past the password reset screen. Pressing the password reset button does nothing when the program is in `Reset` programMode.
Re-do the password reset steps. https://codeberg.org/Discord-OTP-Forcer/Discord-OTP-Forcer/wiki/How-to-setup-and-use#how-to-get-your-token

## I'm using my system/browser in a language other than American English and the program isn't working for me
To fix this, change your system/browser language to English (US). The locale for the browser should be `en-US`.

### Linux
One user says this worked, when he was using Chromium in GNU/Linux:
> I solved it executing my desktop env in LANG=en_US.UTF-8, maybe this can be fixed opening chromium with english LANG in env (tried that with chromium.desktop, but when it opens the chromium window, it opens with the default LANG and not the chromium.desktop I choose)
I.e, open Chrome/Chromium after setting the environment variable LANG/LOCALE to English. (how to do this depends on your os and browser individually, I don't know how it works)

Basically, this program works by detecting strings on the pages only in the English (US) version of the Discord website. Thus if your system or browser uses another language such as Spanish, French, German, etc the program won't detect it and hence won't be able to work.