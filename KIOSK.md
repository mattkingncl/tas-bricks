# Tasmania in Bricks: running the open-day kiosk

This guide is for whoever sets up and looks after the touch-screen exhibit. You need no knowledge of how the software works. It covers the one-time set-up of the PC, starting and stopping the exhibit each day, what visitors and staff do at the stand, and how to adjust the settings, including 3D depth.

---

## 1. What the exhibit is

*Tasmania in Bricks* is a web page that builds real Tasmanian landscapes out of virtual LEGO-sized bricks: Cradle Mountain, Hobart and kunanyi, the whole state with Bass Strait, and others. It runs in the Chrome web browser from

> https://tas-bricks.geodesy1.cloud.edu.au/

Adding `?kiosk` to the address switches on **kiosk mode**, which is designed for a large touch screen at a public stand:

- **Large controls.** The buttons and text are sized for fingers and for reading from a metre or two away.
- **Locked down.** The page cannot be zoomed, scrolled or dragged around, the model cannot be pushed off screen, and long-press menus are disabled.
- **Attract loop.** When nobody has touched the screen for a while, the exhibit resets itself, shows a **"Touch to explore"** prompt and slowly turns the model. Every minute it moves between Cradle Mountain, All of Tasmania and Hobart.
- **3D button.** A **3D (red/cyan glasses)** button turns on a 3D view for paper red/cyan glasses.

The public website is not affected. Kiosk mode only appears when `?kiosk` is in the address.

---

## 2. What you need

| Item | Notes |
|---|---|
| **Touch screen** | A 55" 4K touch display with built-in touch (for example the MoCow 55"). Its touch connects to the PC by a USB cable, and its picture by HDMI. |
| **PC** | Any Windows PC that can run current Google Chrome. A mini PC mounted on the back of the screen is fine. A PC with better graphics runs the high-detail views more smoothly (see section 7). |
| **Internet** | A reliable connection. The exhibit loads its data from the university's server. |
| **Keyboard** (for setting up only) | Needed to start, stop and change settings. Keep it out of reach of visitors. |
| **Red/cyan 3D glasses** | Paper or plastic anaglyph glasses, **red lens on the left eye**. Only needed for the 3D button. |

---

## 3. One-time set-up of the PC

Do this once, well before the event, then test it (section 9).

### 3.1 Connect the screen
1. Connect the screen's **HDMI** input to the PC.
2. Connect the screen's **touch USB** port to a USB port on the PC. Without this cable, the picture works but touch does not.
3. In Windows, open **Settings › System › Display**. Check that the screen is detected at **3840 × 2160** and set **Scale** to **200 %**. This keeps the 3D model fast while the text stays sharp.

### 3.2 Install Google Chrome
Install the current Google Chrome from https://www.google.com/chrome/ and let it update.

### 3.3 Create the kiosk shortcut
1. Right-click on the desktop and choose **New › Shortcut**.
2. For the location, paste the whole line below as one line:

   ```
   "C:\Program Files\Google\Chrome\Application\chrome.exe" --kiosk "https://tas-bricks.geodesy1.cloud.edu.au/?kiosk" --disable-pinch --overscroll-history-navigation=0 --no-first-run --noerrdialogs --disable-session-crashed-bubble --disable-features=TranslateUI --user-data-dir=C:\tas-kiosk
   ```

3. Name the shortcut **Tasmania in Bricks kiosk**.

What the parts of that line do:

- `--kiosk` opens Chrome full screen, with no address bar or tabs.
- The address in quotes is the page to show. The settings in section 6 are added to the end of this address.
- `--disable-pinch` and `--overscroll-history-navigation=0` stop a pinch from zooming the whole page and a swipe from going "back".
- The other options stop Chrome's pop-ups (first-run screens, crash and translate bubbles).
- `--user-data-dir=C:\tas-kiosk` gives the kiosk its own clean Chrome profile, separate from anyone's personal browsing.

### 3.4 Stop Windows getting in the way
- **Sleep and screen saver.** In **Settings › System › Power**, set screen and sleep to **Never**, and turn the screen saver off.
- **Touch gestures.** In **Settings › Bluetooth & devices › Touch**, turn off **Three- and four-finger touch gestures**.
- **Edge swipes.** These would otherwise open Windows panels from the screen edges. On Windows Pro, run `gpedit.msc` and go to **Computer Configuration › Administrative Templates › Windows Components › Edge UI**. Set **Allow edge swipe** to **Disabled**.
- **Notifications.** Turn on **Do not disturb** (Settings › System › Notifications), so no pop-ups appear over the exhibit.
- **Updates.** Pause Windows Update for the day of the event.

### 3.5 Optional: start automatically when the PC starts
Press **Windows + R**, type `shell:startup` and press Enter. Copy the kiosk shortcut into the folder that opens. The exhibit will then start by itself after the PC logs in.

---

## 4. Starting and stopping each day

**To start:** double-click the **Tasmania in Bricks kiosk** shortcut. It loads in a few seconds and opens on Cradle Mountain with the "Touch to explore" prompt.

**To stop:** with the keyboard, press **Alt + F4**.

**To restart after a problem:** press Alt + F4, then double-click the shortcut again. A restart puts everything back to its starting state.

---

## 5. Using it at the stand

### What visitors do
| Gesture | Effect |
|---|---|
| One finger, drag | Turn the model around |
| Two fingers, pinch | Zoom in and out |
| Two fingers, drag | Slide the model across the screen |
| Quick tap on the model | An information card for that brick: height, land cover, rock type, fire history, ice age. A red pin marks the spot. Tap **×** to close. |

The first touch stops the attract loop and also acts as a normal touch.

### Controls in the right-hand panel (useful for staff)
- **Scene:** choose a landscape. The exhibit focuses on **Cradle Mountain**, **All of Tasmania** and **Hobart & kunanyi**.
- **Explore › Water drop:** switches to All of Tasmania. Tap the land to release a raindrop and watch it run downhill to the sea, with its catchment outlined in red.
- **View:** jump to a preset viewpoint. The first button is each scene's best view.
- **Resolution:** the size of a brick on the ground. Smaller sizes show more detail but are slower to build and draw.
- **Vertical scale:** how much heights are exaggerated.
- **Sea level** (coastal scenes): drag to raise or lower the sea. The **−120 m ice age** mark shows the land bridge across Bass Strait.
- **Toggles:** Ice age, Labels, Canopy, Geology map, Fire history, Spring snow, and **3D (red/cyan glasses)**.
- **Build step:** slide to watch the model being built layer by layer.

### 3D mode
1. Tap **3D (red/cyan glasses)**. A **"3D · wear the red/cyan glasses"** badge appears under the title, the title itself turns 3D, and the map labels are hidden. Labels can't be shown in 3D because they would float at the wrong depth.
2. Visitors put the glasses on with the **red lens on the left eye**.
3. Tap the button again to return to normal (2D).

In 3D, colours shift. In particular, water looks purple; that's normal for red/cyan 3D. The exhibit always returns to 2D when it resets after being left idle, in case the next visitor has no glasses.

### When nobody touches it
After **90 seconds** without a touch, the exhibit:
- closes any information card;
- turns 3D off and restores the default layers;
- returns to Cradle Mountain;
- starts the slow-turning attract loop, moving between Cradle Mountain, All of Tasmania and Hobart every **60 seconds**.

All these times can be changed (section 6).

---

## 6. Adjusting the settings

All settings go on the **end of the web address** in the kiosk shortcut, each starting with `&`. To change them:

1. Right-click the kiosk shortcut, choose **Properties**, and edit the **Target** box.
2. Change only the address part, the text in quotes after `--kiosk`.
3. Click **OK**, close the kiosk (Alt + F4), and start it again.

For example, this address waits 2 minutes before resetting, shows each scene for 90 seconds, and uses gentler 3D:

```
"https://tas-bricks.geodesy1.cloud.edu.au/?kiosk&idle=120&tour=90&depth=0.4"
```

| Setting | What it does | Default | Examples |
|---|---|---|---|
| `?kiosk` | Turns kiosk mode on and sizes the controls to the screen automatically. **Must always be first.** | (automatic size) | `?kiosk=1.5` fixes the control size at 1.5× normal. Use it if the panel looks too big or too small. |
| `&idle=` | Seconds without a touch before the exhibit resets and starts the attract loop | `90` | `&idle=180` waits 3 minutes. |
| `&tour=` | Seconds each scene is shown during the attract loop | `60` | `&tour=0` stays on the home scene, just turning. |
| `&home=` | The scene to reset to | `cradle` | `&home=tasmania`, `&home=hobart` |
| `&scenes=` | The scenes the attract loop visits, in order, separated by commas (no spaces) | `cradle,tasmania,hobart` | `&scenes=cradle,hobart` |
| `&depth=` | **3D depth** (see below) | `0.6` | `&depth=0.4` gentler, `&depth=0.8` deeper |
| `&dpr=` | Drawing sharpness. Higher is sharper but slower. | `1` | `&dpr=1.5` on a fast PC |

Scene names for `home` and `scenes`: `cradle`, `tasmania`, `hobart`, `gorge`, `freycinet`, `tasman`, `stclair`, `ossa`, `frenchmans`, `federation`, `nut`.

### 6.1 Setting the 3D depth
**What the number means.** In 3D, each eye sees a slightly different picture. The two pictures are drawn side by side on the screen, a small distance apart. The `depth` setting is the largest allowed separation, as a **percentage of the screen width**. The exhibit recalculates it every frame as the model is turned or zoomed, so the nearest part of the model always floats out of the screen by that amount. The point the model turns around sits exactly on the screen, and the far parts sit a little behind it.

On a 55" screen, which is about 1.22 m wide:

| `depth` | Separation on the screen | Comfort for someone **at arm's length (0.5 m)** | Impression for people **2–3 m back** |
|---|---|---|---|
| `0.4` | about 5 mm | very comfortable | quite flat |
| **`0.6` (default)** | about 7 mm | comfortable (inside the usual 1° limit) | modest depth |
| `0.8` | about 10 mm | at the limit; some people will strain | good depth |
| `1.0` | about 12 mm | too strong up close | strong depth |

**Why there is a trade-off.** The same picture looks deeper the further away you stand, but your eyes find it harder to merge the closer you stand. The default is set for the person touching the screen. Raise it only if the 3D is mostly being watched from a distance.

**How to tune it on the day, with glasses on:**
1. Start at the default (0.6). Stand where visitors will stand, about arm's length from the screen.
2. Turn the model and zoom in and out. The picture should merge easily into one 3D image without eye strain.
3. If anyone reports strain or sees double, lower it, to `&depth=0.4` or `0.5`. If it looks flat, try `0.7` or `0.8`, and check at arm's length again.
4. Children's eyes are closer together, so they see slightly *more* depth than adults from the same picture. Eye strain, however, depends on the angle between the two pictures as seen from where you stand, which is the same for everyone, so a setting that is comfortable for adults at arm's length is comfortable for children too.

**Ghosting.** A faint second image ("ghosting") around bright white peaks or against dark water is normal with red/cyan glasses and gets stronger with more depth. Lowering `depth` reduces it. Good-quality glasses, with lenses that are deep red and clear cyan, also help.

---

## 7. If it runs slowly

The exhibit draws a lot of bricks; Cradle Mountain at its finest detail has about 150,000. A modest PC, especially one with only built-in graphics, may stutter at the finest detail, and 3D roughly doubles the work. In order of effect:

1. Check that Windows scaling is **200 %** (section 3.1) and that `dpr` is **1** or left out.
2. Tap a coarser **Resolution**, for example 50 m instead of 25 m for Cradle.
3. Use 3D on coarser resolutions only.
4. For the longer term, a PC with a better graphics card removes the problem.

---

## 8. Troubleshooting

| Problem | What to do |
|---|---|
| Blank or grey screen, or "Could not load scene data" | The internet connection or the server is down. Check the PC's connection, then restart the kiosk (Alt + F4, then the shortcut). |
| "Sorting bricks…" stays on screen | The scene is still being built. Fine-detail scenes can take several seconds on a slow PC. If it never clears, restart the kiosk. |
| The picture works but touch does nothing | The screen's touch USB cable is unplugged or in the wrong port. Reconnect it and restart the kiosk. |
| Touches land in the wrong place | Run Windows **Calibrate the screen for pen or touch input** (search for "calibrate"). |
| The whole page zooms when pinched | Chrome was started without the shortcut. Close it and use the kiosk shortcut. |
| The model has been dragged somewhere odd | Tap the first **View** button, or leave it alone; it resets after the idle time. |
| Windows panels slide in from the edges | Edge swipes are still on (section 3.4). |
| No way to get out of the kiosk | Plug in a keyboard and press **Alt + F4**. |
| 3D looks wrong (flat or inside-out) | Make sure the **red lens is on the left eye**. |

---

## 9. Checklist before the event

- [ ] Shortcut starts the exhibit full screen on Cradle Mountain with "Touch to explore".
- [ ] One-finger turn, two-finger zoom and move, and tap-for-card all work.
- [ ] **Water drop**: a raindrop released on All of Tasmania runs to the sea.
- [ ] The **3D** button works with the glasses, and the depth is comfortable at arm's length (section 6.1).
- [ ] Left untouched for 90 seconds, it resets and starts the attract loop.
- [ ] The screen doesn't sleep after 30 minutes untouched.
- [ ] Cradle Mountain, All of Tasmania and Hobart turn smoothly on this PC.
- [ ] A keyboard is available, but out of visitors' reach.
- [ ] Glasses are cleaned and ready.

---

## 10. For the maintainer

- The code lives in the GitHub repository `mattkingncl/tas-bricks`. The kiosk behaviour is in `tas-template.html`, in the sections headed *KIOSK SETTINGS* and *Kiosk behaviour*, and the 3D rendering is under *3D: red/cyan anaglyph*.
- The web server is the Nectar VM `tas-bricks`. After updating the repository there, run `./run_all.sh site` to rebuild the page in `/srv/www`. The kiosk picks the change up the next time it is started.
- **How the 3D is drawn:**
  - **Two cameras.** Each eye has its own camera, set apart by an eye separation chosen every frame so the model's on-screen separation stays within `depth` per cent of the width either side of the screen.
  - **Model depth.** The cameras use an off-axis (sheared) projection, so the orbit centre sits in the screen plane.
  - **Colour.** The two images are combined with the Dubois (2001) red/cyan colour matrices, applied after tone mapping.
  - **Title.** The title's 3D effect is plain CSS: a cyan copy for the left eye shifted right and a red copy for the right eye shifted left, giving 0.5 % of the width in front of the screen.
