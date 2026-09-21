# CalDART theme previews

Every theme shipped in `frontend/src/styles/themes/`, shot against the seeded demo site.
Open `index.html` in a browser for the clickable gallery.

Regenerate: start a seeded server the way `make e2e` does, then
`cd frontend && npm run theme-previews`.

## sierra

The default: warm paper, deep conifer, signal orange.

| Shot | File |
| --- | --- |
| Public home | `sierra/site-home.png` |
| Public inner page | `sierra/site-inner.png` |
| Portal dashboard | `sierra/portal-dashboard.png` |
| Member profile | `sierra/portal-profile.png` |
| Home at 420px | `sierra/mobile-home.png` |

### Palette

| Token | Value |
| --- | --- |
| `--color-bg` | `#f4f1ea` |
| `--color-bg-raised` | `#fbfaf6` |
| `--color-bg-sunken` | `#ebe7dd` |
| `--color-fg` | `#1b1f24` |
| `--color-primary` | `#1f4d3a` |
| `--color-primary-fg` | `#f7f5ef` |
| `--color-primary-hover` | `#17392b` |
| `--color-accent` | `#bb4623` |
| `--color-secondary` | `#f2a900` |
| `--color-rule` | `#d9d3c7` |
| `--color-rule-strong` | `#b9b1a0` |
| `--color-muted` | `#64676e` |
| `--color-ok` | `#27693f` |
| `--color-warn` | `#825900` |
| `--color-bad` | `#ab3628` |
| `--color-focus` | `#1f4d3a` |

### Fonts

| Role | Family | Package |
| --- | --- | --- |
| Display | Fraunces | `@fontsource-variable/fraunces` |
| Body | IBM Plex Sans | `@fontsource/ibm-plex-sans` |
| Mono | IBM Plex Mono | `@fontsource/ibm-plex-mono` |

### Contrast (WCAG 2.1 AA)

| Pair | Ratio | Needs | |
| --- | --- | --- | --- |
| fg on bg | 14.68:1 | 4.5:1 | pass |
| fg on bg-raised | 15.86:1 | 4.5:1 | pass |
| fg on bg-sunken | 13.41:1 | 4.5:1 | pass |
| muted on bg | 5.02:1 | 4.5:1 | pass |
| muted on bg-raised | 5.42:1 | 4.5:1 | pass |
| muted on bg-sunken | 4.59:1 | 4.5:1 | pass |
| primary on bg | 8.54:1 | 4.5:1 | pass |
| primary on bg-raised | 9.22:1 | 4.5:1 | pass |
| primary-fg on primary | 8.83:1 | 4.5:1 | pass |
| primary-fg on primary-hover | 11.63:1 | 4.5:1 | pass |
| accent on bg | 4.64:1 | 4.5:1 | pass |
| ok on bg | 5.86:1 | 4.5:1 | pass |
| warn on bg | 5.51:1 | 4.5:1 | pass |
| bad on bg | 5.66:1 | 4.5:1 | pass |
| ok on ok-bg over bg | 4.92:1 | 4.5:1 | pass |
| warn on warn-bg over bg | 4.68:1 | 4.5:1 | pass |
| bad on bad-bg over bg | 4.71:1 | 4.5:1 | pass |
| focus on bg | 8.54:1 | 3:1 | pass |

### Reproduce

- Theme file: `frontend/src/styles/themes/sierra.css`
- Attribute the server renders: `<html data-theme="sierra">`
- Select it in Wagtail: **Settings -> Site settings -> Theme**, then save.
- Preview without saving, as a website or system administrator: `https://<your-site>/?theme=sierra`
- Font packages: `npm install @fontsource-variable/fraunces @fontsource/ibm-plex-sans @fontsource/ibm-plex-mono`

## pacific

Cooler paper and a deep pacific blue primary.

| Shot | File |
| --- | --- |
| Public home | `pacific/site-home.png` |
| Public inner page | `pacific/site-inner.png` |
| Portal dashboard | `pacific/portal-dashboard.png` |
| Member profile | `pacific/portal-profile.png` |
| Home at 420px | `pacific/mobile-home.png` |

### Palette

| Token | Value |
| --- | --- |
| `--color-bg` | `#f6f7f5` |
| `--color-bg-raised` | `#fdfdfc` |
| `--color-bg-sunken` | `#e9ecea` |
| `--color-fg` | `#14212b` |
| `--color-primary` | `#0f3d5c` |
| `--color-primary-fg` | `#f4f8fa` |
| `--color-primary-hover` | `#0a2c43` |
| `--color-accent` | `#bb4623` |
| `--color-secondary` | `#8da9b8` |
| `--color-rule` | `#d3dadd` |
| `--color-rule-strong` | `#adb9bf` |
| `--color-muted` | `#5c6b74` |
| `--color-ok` | `#27693f` |
| `--color-warn` | `#825900` |
| `--color-bad` | `#ab3628` |
| `--color-focus` | `#0f3d5c` |

### Fonts

| Role | Family | Package |
| --- | --- | --- |
| Display | Fraunces | `@fontsource-variable/fraunces` |
| Body | IBM Plex Sans | `@fontsource/ibm-plex-sans` |
| Mono | IBM Plex Mono | `@fontsource/ibm-plex-mono` |

### Contrast (WCAG 2.1 AA)

| Pair | Ratio | Needs | |
| --- | --- | --- | --- |
| fg on bg | 15.24:1 | 4.5:1 | pass |
| fg on bg-raised | 16.09:1 | 4.5:1 | pass |
| fg on bg-sunken | 13.77:1 | 4.5:1 | pass |
| muted on bg | 5.13:1 | 4.5:1 | pass |
| muted on bg-raised | 5.41:1 | 4.5:1 | pass |
| muted on bg-sunken | 4.63:1 | 4.5:1 | pass |
| primary on bg | 10.61:1 | 4.5:1 | pass |
| primary on bg-raised | 11.20:1 | 4.5:1 | pass |
| primary-fg on primary | 10.67:1 | 4.5:1 | pass |
| primary-fg on primary-hover | 13.52:1 | 4.5:1 | pass |
| accent on bg | 4.87:1 | 4.5:1 | pass |
| ok on bg | 6.15:1 | 4.5:1 | pass |
| warn on bg | 5.78:1 | 4.5:1 | pass |
| bad on bg | 5.94:1 | 4.5:1 | pass |
| ok on ok-bg over bg | 5.18:1 | 4.5:1 | pass |
| warn on warn-bg over bg | 4.89:1 | 4.5:1 | pass |
| bad on bad-bg over bg | 4.95:1 | 4.5:1 | pass |
| focus on bg | 10.61:1 | 3:1 | pass |

### Reproduce

- Theme file: `frontend/src/styles/themes/pacific.css`
- Attribute the server renders: `<html data-theme="pacific">`
- Select it in Wagtail: **Settings -> Site settings -> Theme**, then save.
- Preview without saving, as a website or system administrator: `https://<your-site>/?theme=pacific`
- Font packages: `npm install @fontsource-variable/fraunces @fontsource/ibm-plex-sans @fontsource/ibm-plex-mono`

## night

The dark counterpart to sierra, with lifted status colors.

| Shot | File |
| --- | --- |
| Public home | `night/site-home.png` |
| Public inner page | `night/site-inner.png` |
| Portal dashboard | `night/portal-dashboard.png` |
| Member profile | `night/portal-profile.png` |
| Home at 420px | `night/mobile-home.png` |

### Palette

| Token | Value |
| --- | --- |
| `--color-bg` | `#151719` |
| `--color-bg-raised` | `#1d2023` |
| `--color-bg-sunken` | `#101214` |
| `--color-fg` | `#ece9e1` |
| `--color-primary` | `#7fb69b` |
| `--color-primary-fg` | `#10201a` |
| `--color-primary-hover` | `#98c9b0` |
| `--color-accent` | `#ff7a52` |
| `--color-secondary` | `#f2c14e` |
| `--color-rule` | `#2c3034` |
| `--color-rule-strong` | `#444a50` |
| `--color-muted` | `#9aa1a8` |
| `--color-ok` | `#6cc08c` |
| `--color-warn` | `#e5b74a` |
| `--color-bad` | `#f0796a` |
| `--color-focus` | `#f2c14e` |

### Fonts

| Role | Family | Package |
| --- | --- | --- |
| Display | Fraunces | `@fontsource-variable/fraunces` |
| Body | IBM Plex Sans | `@fontsource/ibm-plex-sans` |
| Mono | IBM Plex Mono | `@fontsource/ibm-plex-mono` |

### Contrast (WCAG 2.1 AA)

| Pair | Ratio | Needs | |
| --- | --- | --- | --- |
| fg on bg | 14.81:1 | 4.5:1 | pass |
| fg on bg-raised | 13.49:1 | 4.5:1 | pass |
| fg on bg-sunken | 15.47:1 | 4.5:1 | pass |
| muted on bg | 6.88:1 | 4.5:1 | pass |
| muted on bg-raised | 6.26:1 | 4.5:1 | pass |
| muted on bg-sunken | 7.18:1 | 4.5:1 | pass |
| primary on bg | 7.76:1 | 4.5:1 | pass |
| primary on bg-raised | 7.07:1 | 4.5:1 | pass |
| primary-fg on primary | 7.29:1 | 4.5:1 | pass |
| primary-fg on primary-hover | 9.10:1 | 4.5:1 | pass |
| accent on bg | 6.98:1 | 4.5:1 | pass |
| ok on bg | 8.18:1 | 4.5:1 | pass |
| warn on bg | 9.59:1 | 4.5:1 | pass |
| bad on bg | 6.55:1 | 4.5:1 | pass |
| ok on ok-bg over bg | 6.27:1 | 4.5:1 | pass |
| warn on warn-bg over bg | 7.12:1 | 4.5:1 | pass |
| bad on bad-bg over bg | 5.24:1 | 4.5:1 | pass |
| focus on bg | 10.71:1 | 3:1 | pass |

### Reproduce

- Theme file: `frontend/src/styles/themes/night.css`
- Attribute the server renders: `<html data-theme="night">`
- Select it in Wagtail: **Settings -> Site settings -> Theme**, then save.
- Preview without saving, as a website or system administrator: `https://<your-site>/?theme=night`
- Font packages: `npm install @fontsource-variable/fraunces @fontsource/ibm-plex-sans @fontsource/ibm-plex-mono`

## squadron

The CalDART logo on white: cobalt, crimson, sky, and a lot of air.

| Shot | File |
| --- | --- |
| Public home | `squadron/site-home.png` |
| Public inner page | `squadron/site-inner.png` |
| Portal dashboard | `squadron/portal-dashboard.png` |
| Member profile | `squadron/portal-profile.png` |
| Home at 420px | `squadron/mobile-home.png` |

### Palette

| Token | Value |
| --- | --- |
| `--color-bg` | `#ffffff` |
| `--color-bg-raised` | `#f6f7fb` |
| `--color-bg-sunken` | `#eceef5` |
| `--color-fg` | `#14213d` |
| `--color-primary` | `#1b409a` |
| `--color-primary-fg` | `#ffffff` |
| `--color-primary-hover` | `#142f73` |
| `--color-accent` | `#b8303f` |
| `--color-secondary` | `#4f8fe8` |
| `--color-rule` | `#dde1ec` |
| `--color-rule-strong` | `#a9b2c8` |
| `--color-muted` | `#59627c` |
| `--color-ok` | `#27693f` |
| `--color-warn` | `#825900` |
| `--color-bad` | `#ab3628` |
| `--color-focus` | `#1b409a` |

### Fonts

| Role | Family | Package |
| --- | --- | --- |
| Display | Barlow | `@fontsource/barlow` |
| Body | Source Sans 3 | `@fontsource-variable/source-sans-3` |
| Mono | JetBrains Mono | `@fontsource-variable/jetbrains-mono` |

### Contrast (WCAG 2.1 AA)

| Pair | Ratio | Needs | |
| --- | --- | --- | --- |
| fg on bg | 15.97:1 | 4.5:1 | pass |
| fg on bg-raised | 14.92:1 | 4.5:1 | pass |
| fg on bg-sunken | 13.78:1 | 4.5:1 | pass |
| muted on bg | 6.06:1 | 4.5:1 | pass |
| muted on bg-raised | 5.66:1 | 4.5:1 | pass |
| muted on bg-sunken | 5.23:1 | 4.5:1 | pass |
| primary on bg | 9.35:1 | 4.5:1 | pass |
| primary on bg-raised | 8.73:1 | 4.5:1 | pass |
| primary-fg on primary | 9.35:1 | 4.5:1 | pass |
| primary-fg on primary-hover | 12.47:1 | 4.5:1 | pass |
| accent on bg | 5.94:1 | 4.5:1 | pass |
| ok on bg | 6.61:1 | 4.5:1 | pass |
| warn on bg | 6.22:1 | 4.5:1 | pass |
| bad on bg | 6.38:1 | 4.5:1 | pass |
| ok on ok-bg over bg | 5.54:1 | 4.5:1 | pass |
| warn on warn-bg over bg | 5.23:1 | 4.5:1 | pass |
| bad on bad-bg over bg | 5.30:1 | 4.5:1 | pass |
| focus on bg | 9.35:1 | 3:1 | pass |

### Reproduce

- Theme file: `frontend/src/styles/themes/squadron.css`
- Attribute the server renders: `<html data-theme="squadron">`
- Select it in Wagtail: **Settings -> Site settings -> Theme**, then save.
- Preview without saving, as a website or system administrator: `https://<your-site>/?theme=squadron`
- Font packages: `npm install @fontsource/barlow @fontsource-variable/source-sans-3 @fontsource-variable/jetbrains-mono`

## flight-deck

The logo after dark: navy instruments, cobalt tint, crimson and amber.

| Shot | File |
| --- | --- |
| Public home | `flight-deck/site-home.png` |
| Public inner page | `flight-deck/site-inner.png` |
| Portal dashboard | `flight-deck/portal-dashboard.png` |
| Member profile | `flight-deck/portal-profile.png` |
| Home at 420px | `flight-deck/mobile-home.png` |

### Palette

| Token | Value |
| --- | --- |
| `--color-bg` | `#0f1a33` |
| `--color-bg-raised` | `#16233f` |
| `--color-bg-sunken` | `#0a1226` |
| `--color-fg` | `#e8ecf5` |
| `--color-primary` | `#7ea2ff` |
| `--color-primary-fg` | `#0f1a33` |
| `--color-primary-hover` | `#9db8ff` |
| `--color-accent` | `#ef6b78` |
| `--color-secondary` | `#ffc857` |
| `--color-rule` | `#26314d` |
| `--color-rule-strong` | `#465170` |
| `--color-muted` | `#a4afc9` |
| `--color-ok` | `#63d0a0` |
| `--color-warn` | `#ffc857` |
| `--color-bad` | `#f4818c` |
| `--color-focus` | `#ffc857` |

### Fonts

| Role | Family | Package |
| --- | --- | --- |
| Display | Exo 2 | `@fontsource-variable/exo-2` |
| Body | Inter | `@fontsource-variable/inter` |
| Mono | IBM Plex Mono | `@fontsource/ibm-plex-mono` |

### Contrast (WCAG 2.1 AA)

| Pair | Ratio | Needs | |
| --- | --- | --- | --- |
| fg on bg | 14.60:1 | 4.5:1 | pass |
| fg on bg-raised | 13.18:1 | 4.5:1 | pass |
| fg on bg-sunken | 15.74:1 | 4.5:1 | pass |
| muted on bg | 7.86:1 | 4.5:1 | pass |
| muted on bg-raised | 7.10:1 | 4.5:1 | pass |
| muted on bg-sunken | 8.47:1 | 4.5:1 | pass |
| primary on bg | 6.99:1 | 4.5:1 | pass |
| primary on bg-raised | 6.31:1 | 4.5:1 | pass |
| primary-fg on primary | 6.99:1 | 4.5:1 | pass |
| primary-fg on primary-hover | 8.83:1 | 4.5:1 | pass |
| accent on bg | 5.79:1 | 4.5:1 | pass |
| ok on bg | 9.10:1 | 4.5:1 | pass |
| warn on bg | 11.23:1 | 4.5:1 | pass |
| bad on bg | 6.88:1 | 4.5:1 | pass |
| ok on ok-bg over bg | 6.75:1 | 4.5:1 | pass |
| warn on warn-bg over bg | 8.08:1 | 4.5:1 | pass |
| bad on bad-bg over bg | 5.50:1 | 4.5:1 | pass |
| focus on bg | 11.23:1 | 3:1 | pass |

### Reproduce

- Theme file: `frontend/src/styles/themes/flight-deck.css`
- Attribute the server renders: `<html data-theme="flight-deck">`
- Select it in Wagtail: **Settings -> Site settings -> Theme**, then save.
- Preview without saving, as a website or system administrator: `https://<your-site>/?theme=flight-deck`
- Font packages: `npm install @fontsource-variable/exo-2 @fontsource-variable/inter @fontsource/ibm-plex-mono`

## contrail

The logo gone light and airy: high sky paper, cobalt, crimson.

| Shot | File |
| --- | --- |
| Public home | `contrail/site-home.png` |
| Public inner page | `contrail/site-inner.png` |
| Portal dashboard | `contrail/portal-dashboard.png` |
| Member profile | `contrail/portal-profile.png` |
| Home at 420px | `contrail/mobile-home.png` |

### Palette

| Token | Value |
| --- | --- |
| `--color-bg` | `#eef4fb` |
| `--color-bg-raised` | `#ffffff` |
| `--color-bg-sunken` | `#dfe8f5` |
| `--color-fg` | `#1a2333` |
| `--color-primary` | `#1b409a` |
| `--color-primary-fg` | `#ffffff` |
| `--color-primary-hover` | `#142f73` |
| `--color-accent` | `#b02c3a` |
| `--color-secondary` | `#3b7dd8` |
| `--color-rule` | `#cfdcec` |
| `--color-rule-strong` | `#a0b2cb` |
| `--color-muted` | `#515c70` |
| `--color-ok` | `#27693f` |
| `--color-warn` | `#825900` |
| `--color-bad` | `#ab3628` |
| `--color-focus` | `#1b409a` |

### Fonts

| Role | Family | Package |
| --- | --- | --- |
| Display | Titillium Web | `@fontsource/titillium-web` |
| Body | Open Sans | `@fontsource-variable/open-sans` |
| Mono | Roboto Mono | `@fontsource-variable/roboto-mono` |

### Contrast (WCAG 2.1 AA)

| Pair | Ratio | Needs | |
| --- | --- | --- | --- |
| fg on bg | 14.24:1 | 4.5:1 | pass |
| fg on bg-raised | 15.76:1 | 4.5:1 | pass |
| fg on bg-sunken | 12.76:1 | 4.5:1 | pass |
| muted on bg | 6.09:1 | 4.5:1 | pass |
| muted on bg-raised | 6.74:1 | 4.5:1 | pass |
| muted on bg-sunken | 5.46:1 | 4.5:1 | pass |
| primary on bg | 8.44:1 | 4.5:1 | pass |
| primary on bg-raised | 9.35:1 | 4.5:1 | pass |
| primary-fg on primary | 9.35:1 | 4.5:1 | pass |
| primary-fg on primary-hover | 12.47:1 | 4.5:1 | pass |
| accent on bg | 5.81:1 | 4.5:1 | pass |
| ok on bg | 5.97:1 | 4.5:1 | pass |
| warn on bg | 5.62:1 | 4.5:1 | pass |
| bad on bg | 5.77:1 | 4.5:1 | pass |
| ok on ok-bg over bg | 5.02:1 | 4.5:1 | pass |
| warn on warn-bg over bg | 4.74:1 | 4.5:1 | pass |
| bad on bad-bg over bg | 4.80:1 | 4.5:1 | pass |
| focus on bg | 8.44:1 | 3:1 | pass |

### Reproduce

- Theme file: `frontend/src/styles/themes/contrail.css`
- Attribute the server renders: `<html data-theme="contrail">`
- Select it in Wagtail: **Settings -> Site settings -> Theme**, then save.
- Preview without saving, as a website or system administrator: `https://<your-site>/?theme=contrail`
- Font packages: `npm install @fontsource/titillium-web @fontsource-variable/open-sans @fontsource-variable/roboto-mono`

## sectional

An aeronautical chart: chart cream, chart blue, airspace magenta, terrain tan.

| Shot | File |
| --- | --- |
| Public home | `sectional/site-home.png` |
| Public inner page | `sectional/site-inner.png` |
| Portal dashboard | `sectional/portal-dashboard.png` |
| Member profile | `sectional/portal-profile.png` |
| Home at 420px | `sectional/mobile-home.png` |

### Palette

| Token | Value |
| --- | --- |
| `--color-bg` | `#f7f3e8` |
| `--color-bg-raised` | `#fffdf7` |
| `--color-bg-sunken` | `#ece5d3` |
| `--color-fg` | `#24211c` |
| `--color-primary` | `#2c5aa0` |
| `--color-primary-fg` | `#ffffff` |
| `--color-primary-hover` | `#204478` |
| `--color-accent` | `#a72f80` |
| `--color-secondary` | `#b3833f` |
| `--color-rule` | `#ded5c0` |
| `--color-rule-strong` | `#b5a88d` |
| `--color-muted` | `#5d584c` |
| `--color-ok` | `#27693f` |
| `--color-warn` | `#825900` |
| `--color-bad` | `#ab3628` |
| `--color-focus` | `#2c5aa0` |

### Fonts

| Role | Family | Package |
| --- | --- | --- |
| Display | Manrope | `@fontsource-variable/manrope` |
| Body | Source Sans 3 | `@fontsource-variable/source-sans-3` |
| Mono | Roboto Mono | `@fontsource-variable/roboto-mono` |

### Contrast (WCAG 2.1 AA)

| Pair | Ratio | Needs | |
| --- | --- | --- | --- |
| fg on bg | 14.47:1 | 4.5:1 | pass |
| fg on bg-raised | 15.77:1 | 4.5:1 | pass |
| fg on bg-sunken | 12.77:1 | 4.5:1 | pass |
| muted on bg | 6.39:1 | 4.5:1 | pass |
| muted on bg-raised | 6.96:1 | 4.5:1 | pass |
| muted on bg-sunken | 5.64:1 | 4.5:1 | pass |
| primary on bg | 6.16:1 | 4.5:1 | pass |
| primary on bg-raised | 6.71:1 | 4.5:1 | pass |
| primary-fg on primary | 6.82:1 | 4.5:1 | pass |
| primary-fg on primary-hover | 9.72:1 | 4.5:1 | pass |
| accent on bg | 5.63:1 | 4.5:1 | pass |
| ok on bg | 5.96:1 | 4.5:1 | pass |
| warn on bg | 5.61:1 | 4.5:1 | pass |
| bad on bg | 5.76:1 | 4.5:1 | pass |
| ok on ok-bg over bg | 5.01:1 | 4.5:1 | pass |
| warn on warn-bg over bg | 4.74:1 | 4.5:1 | pass |
| bad on bad-bg over bg | 4.80:1 | 4.5:1 | pass |
| focus on bg | 6.16:1 | 3:1 | pass |

### Reproduce

- Theme file: `frontend/src/styles/themes/sectional.css`
- Attribute the server renders: `<html data-theme="sectional">`
- Select it in Wagtail: **Settings -> Site settings -> Theme**, then save.
- Preview without saving, as a website or system administrator: `https://<your-site>/?theme=sectional`
- Font packages: `npm install @fontsource-variable/manrope @fontsource-variable/source-sans-3 @fontsource-variable/roboto-mono`

## tarmac

Industrial neutrals: concrete, asphalt, safety yellow on surfaces only.

| Shot | File |
| --- | --- |
| Public home | `tarmac/site-home.png` |
| Public inner page | `tarmac/site-inner.png` |
| Portal dashboard | `tarmac/portal-dashboard.png` |
| Member profile | `tarmac/portal-profile.png` |
| Home at 420px | `tarmac/mobile-home.png` |

### Palette

| Token | Value |
| --- | --- |
| `--color-bg` | `#f2f2f0` |
| `--color-bg-raised` | `#fafaf9` |
| `--color-bg-sunken` | `#e4e4e1` |
| `--color-fg` | `#1a1c20` |
| `--color-primary` | `#2b2f36` |
| `--color-primary-fg` | `#ffffff` |
| `--color-primary-hover` | `#16181c` |
| `--color-accent` | `#b40d27` |
| `--color-secondary` | `#e3b505` |
| `--color-rule` | `#d8d8d4` |
| `--color-rule-strong` | `#adada8` |
| `--color-muted` | `#5a5e64` |
| `--color-ok` | `#27693f` |
| `--color-warn` | `#825900` |
| `--color-bad` | `#ab3628` |
| `--color-focus` | `#2b2f36` |

### Fonts

| Role | Family | Package |
| --- | --- | --- |
| Display | Archivo | `@fontsource-variable/archivo` |
| Body | Karla | `@fontsource-variable/karla` |
| Mono | Fira Code | `@fontsource-variable/fira-code` |

### Contrast (WCAG 2.1 AA)

| Pair | Ratio | Needs | |
| --- | --- | --- | --- |
| fg on bg | 15.22:1 | 4.5:1 | pass |
| fg on bg-raised | 16.34:1 | 4.5:1 | pass |
| fg on bg-sunken | 13.39:1 | 4.5:1 | pass |
| muted on bg | 5.82:1 | 4.5:1 | pass |
| muted on bg-raised | 6.24:1 | 4.5:1 | pass |
| muted on bg-sunken | 5.12:1 | 4.5:1 | pass |
| primary on bg | 11.99:1 | 4.5:1 | pass |
| primary on bg-raised | 12.87:1 | 4.5:1 | pass |
| primary-fg on primary | 13.44:1 | 4.5:1 | pass |
| primary-fg on primary-hover | 17.77:1 | 4.5:1 | pass |
| accent on bg | 6.19:1 | 4.5:1 | pass |
| ok on bg | 5.89:1 | 4.5:1 | pass |
| warn on bg | 5.55:1 | 4.5:1 | pass |
| bad on bg | 5.69:1 | 4.5:1 | pass |
| ok on ok-bg over bg | 4.95:1 | 4.5:1 | pass |
| warn on warn-bg over bg | 4.68:1 | 4.5:1 | pass |
| bad on bad-bg over bg | 4.74:1 | 4.5:1 | pass |
| focus on bg | 11.99:1 | 3:1 | pass |

### Reproduce

- Theme file: `frontend/src/styles/themes/tarmac.css`
- Attribute the server renders: `<html data-theme="tarmac">`
- Select it in Wagtail: **Settings -> Site settings -> Theme**, then save.
- Preview without saving, as a website or system administrator: `https://<your-site>/?theme=tarmac`
- Font packages: `npm install @fontsource-variable/archivo @fontsource-variable/karla @fontsource-variable/fira-code`

## coastal

The California shoreline: fog paper, ocean teal, sunset coral, dune sand.

| Shot | File |
| --- | --- |
| Public home | `coastal/site-home.png` |
| Public inner page | `coastal/site-inner.png` |
| Portal dashboard | `coastal/portal-dashboard.png` |
| Member profile | `coastal/portal-profile.png` |
| Home at 420px | `coastal/mobile-home.png` |

### Palette

| Token | Value |
| --- | --- |
| `--color-bg` | `#f3f6f7` |
| `--color-bg-raised` | `#ffffff` |
| `--color-bg-sunken` | `#e3e9eb` |
| `--color-fg` | `#1c2a30` |
| `--color-primary` | `#146c7a` |
| `--color-primary-fg` | `#ffffff` |
| `--color-primary-hover` | `#0e515c` |
| `--color-accent` | `#bd4a2a` |
| `--color-secondary` | `#c9a15a` |
| `--color-rule` | `#d2dcdf` |
| `--color-rule-strong` | `#a3b2b7` |
| `--color-muted` | `#54626a` |
| `--color-ok` | `#27693f` |
| `--color-warn` | `#825900` |
| `--color-bad` | `#ab3628` |
| `--color-focus` | `#146c7a` |

### Fonts

| Role | Family | Package |
| --- | --- | --- |
| Display | Lora | `@fontsource-variable/lora` |
| Body | Nunito Sans | `@fontsource-variable/nunito-sans` |
| Mono | Source Code Pro | `@fontsource-variable/source-code-pro` |

### Contrast (WCAG 2.1 AA)

| Pair | Ratio | Needs | |
| --- | --- | --- | --- |
| fg on bg | 13.59:1 | 4.5:1 | pass |
| fg on bg-raised | 14.76:1 | 4.5:1 | pass |
| fg on bg-sunken | 12.03:1 | 4.5:1 | pass |
| muted on bg | 5.80:1 | 4.5:1 | pass |
| muted on bg-raised | 6.30:1 | 4.5:1 | pass |
| muted on bg-sunken | 5.14:1 | 4.5:1 | pass |
| primary on bg | 5.60:1 | 4.5:1 | pass |
| primary on bg-raised | 6.08:1 | 4.5:1 | pass |
| primary-fg on primary | 6.08:1 | 4.5:1 | pass |
| primary-fg on primary-hover | 8.94:1 | 4.5:1 | pass |
| accent on bg | 4.63:1 | 4.5:1 | pass |
| ok on bg | 6.08:1 | 4.5:1 | pass |
| warn on bg | 5.72:1 | 4.5:1 | pass |
| bad on bg | 5.88:1 | 4.5:1 | pass |
| ok on ok-bg over bg | 5.12:1 | 4.5:1 | pass |
| warn on warn-bg over bg | 4.83:1 | 4.5:1 | pass |
| bad on bad-bg over bg | 4.90:1 | 4.5:1 | pass |
| focus on bg | 5.60:1 | 3:1 | pass |

### Reproduce

- Theme file: `frontend/src/styles/themes/coastal.css`
- Attribute the server renders: `<html data-theme="coastal">`
- Select it in Wagtail: **Settings -> Site settings -> Theme**, then save.
- Preview without saving, as a website or system administrator: `https://<your-site>/?theme=coastal`
- Font packages: `npm install @fontsource-variable/lora @fontsource-variable/nunito-sans @fontsource-variable/source-code-pro`

## slate

Cool corporate: slate blue-gray, amber emphasis, a teal supporting hue.

| Shot | File |
| --- | --- |
| Public home | `slate/site-home.png` |
| Public inner page | `slate/site-inner.png` |
| Portal dashboard | `slate/portal-dashboard.png` |
| Member profile | `slate/portal-profile.png` |
| Home at 420px | `slate/mobile-home.png` |

### Palette

| Token | Value |
| --- | --- |
| `--color-bg` | `#f5f7fa` |
| `--color-bg-raised` | `#ffffff` |
| `--color-bg-sunken` | `#e8ecf1` |
| `--color-fg` | `#1f2933` |
| `--color-primary` | `#34495e` |
| `--color-primary-fg` | `#ffffff` |
| `--color-primary-hover` | `#22303f` |
| `--color-accent` | `#a94c08` |
| `--color-secondary` | `#2f7f9e` |
| `--color-rule` | `#dbe1e9` |
| `--color-rule-strong` | `#a7b1c0` |
| `--color-muted` | `#586475` |
| `--color-ok` | `#27693f` |
| `--color-warn` | `#825900` |
| `--color-bad` | `#ab3628` |
| `--color-focus` | `#34495e` |

### Fonts

| Role | Family | Package |
| --- | --- | --- |
| Display | Merriweather | `@fontsource-variable/merriweather` |
| Body | Work Sans | `@fontsource-variable/work-sans` |
| Mono | DM Mono | `@fontsource/dm-mono` |

### Contrast (WCAG 2.1 AA)

| Pair | Ratio | Needs | |
| --- | --- | --- | --- |
| fg on bg | 13.75:1 | 4.5:1 | pass |
| fg on bg-raised | 14.76:1 | 4.5:1 | pass |
| fg on bg-sunken | 12.44:1 | 4.5:1 | pass |
| muted on bg | 5.60:1 | 4.5:1 | pass |
| muted on bg-raised | 6.01:1 | 4.5:1 | pass |
| muted on bg-sunken | 5.06:1 | 4.5:1 | pass |
| primary on bg | 8.66:1 | 4.5:1 | pass |
| primary on bg-raised | 9.29:1 | 4.5:1 | pass |
| primary-fg on primary | 9.29:1 | 4.5:1 | pass |
| primary-fg on primary-hover | 13.44:1 | 4.5:1 | pass |
| accent on bg | 5.25:1 | 4.5:1 | pass |
| ok on bg | 6.16:1 | 4.5:1 | pass |
| warn on bg | 5.79:1 | 4.5:1 | pass |
| bad on bg | 5.95:1 | 4.5:1 | pass |
| ok on ok-bg over bg | 5.18:1 | 4.5:1 | pass |
| warn on warn-bg over bg | 4.89:1 | 4.5:1 | pass |
| bad on bad-bg over bg | 4.96:1 | 4.5:1 | pass |
| focus on bg | 8.66:1 | 3:1 | pass |

### Reproduce

- Theme file: `frontend/src/styles/themes/slate.css`
- Attribute the server renders: `<html data-theme="slate">`
- Select it in Wagtail: **Settings -> Site settings -> Theme**, then save.
- Preview without saving, as a website or system administrator: `https://<your-site>/?theme=slate`
- Font packages: `npm install @fontsource-variable/merriweather @fontsource-variable/work-sans @fontsource/dm-mono`

## meridian

High-contrast civic: white, navy, burnt orange, one typeface throughout.

| Shot | File |
| --- | --- |
| Public home | `meridian/site-home.png` |
| Public inner page | `meridian/site-inner.png` |
| Portal dashboard | `meridian/portal-dashboard.png` |
| Member profile | `meridian/portal-profile.png` |
| Home at 420px | `meridian/mobile-home.png` |

### Palette

| Token | Value |
| --- | --- |
| `--color-bg` | `#ffffff` |
| `--color-bg-raised` | `#f8f9fb` |
| `--color-bg-sunken` | `#eef0f4` |
| `--color-fg` | `#0b1220` |
| `--color-primary` | `#0d3b66` |
| `--color-primary-fg` | `#ffffff` |
| `--color-primary-hover` | `#072744` |
| `--color-accent` | `#b03a0a` |
| `--color-secondary` | `#166b64` |
| `--color-rule` | `#dde1e9` |
| `--color-rule-strong` | `#a5aebe` |
| `--color-muted` | `#4b5465` |
| `--color-ok` | `#27693f` |
| `--color-warn` | `#825900` |
| `--color-bad` | `#ab3628` |
| `--color-focus` | `#0d3b66` |

### Fonts

| Role | Family | Package |
| --- | --- | --- |
| Display | Libre Franklin | `@fontsource-variable/libre-franklin` |
| Body | Libre Franklin | `@fontsource-variable/libre-franklin` |
| Mono | Roboto Mono | `@fontsource-variable/roboto-mono` |

### Contrast (WCAG 2.1 AA)

| Pair | Ratio | Needs | |
| --- | --- | --- | --- |
| fg on bg | 18.72:1 | 4.5:1 | pass |
| fg on bg-raised | 17.77:1 | 4.5:1 | pass |
| fg on bg-sunken | 16.41:1 | 4.5:1 | pass |
| muted on bg | 7.62:1 | 4.5:1 | pass |
| muted on bg-raised | 7.24:1 | 4.5:1 | pass |
| muted on bg-sunken | 6.68:1 | 4.5:1 | pass |
| primary on bg | 11.45:1 | 4.5:1 | pass |
| primary on bg-raised | 10.87:1 | 4.5:1 | pass |
| primary-fg on primary | 11.45:1 | 4.5:1 | pass |
| primary-fg on primary-hover | 15.19:1 | 4.5:1 | pass |
| accent on bg | 6.08:1 | 4.5:1 | pass |
| ok on bg | 6.61:1 | 4.5:1 | pass |
| warn on bg | 6.22:1 | 4.5:1 | pass |
| bad on bg | 6.38:1 | 4.5:1 | pass |
| ok on ok-bg over bg | 5.54:1 | 4.5:1 | pass |
| warn on warn-bg over bg | 5.23:1 | 4.5:1 | pass |
| bad on bad-bg over bg | 5.30:1 | 4.5:1 | pass |
| focus on bg | 11.45:1 | 3:1 | pass |

### Reproduce

- Theme file: `frontend/src/styles/themes/meridian.css`
- Attribute the server renders: `<html data-theme="meridian">`
- Select it in Wagtail: **Settings -> Site settings -> Theme**, then save.
- Preview without saving, as a website or system administrator: `https://<your-site>/?theme=meridian`
- Font packages: `npm install @fontsource-variable/libre-franklin @fontsource-variable/roboto-mono`

## monterey-night

Charcoal dark: sea green primary, amber accent, a cool blue support.

| Shot | File |
| --- | --- |
| Public home | `monterey-night/site-home.png` |
| Public inner page | `monterey-night/site-inner.png` |
| Portal dashboard | `monterey-night/portal-dashboard.png` |
| Member profile | `monterey-night/portal-profile.png` |
| Home at 420px | `monterey-night/mobile-home.png` |

### Palette

| Token | Value |
| --- | --- |
| `--color-bg` | `#14171c` |
| `--color-bg-raised` | `#1c2027` |
| `--color-bg-sunken` | `#0f1115` |
| `--color-fg` | `#e6e8ec` |
| `--color-primary` | `#5ec8b8` |
| `--color-primary-fg` | `#0f1115` |
| `--color-primary-hover` | `#7ad6c8` |
| `--color-accent` | `#ffb454` |
| `--color-secondary` | `#8ab4f8` |
| `--color-rule` | `#2a2f38` |
| `--color-rule-strong` | `#474e5a` |
| `--color-muted` | `#98a2b0` |
| `--color-ok` | `#63d2a4` |
| `--color-warn` | `#ffb454` |
| `--color-bad` | `#ff8a80` |
| `--color-focus` | `#ffb454` |

### Fonts

| Role | Family | Package |
| --- | --- | --- |
| Display | Sora | `@fontsource-variable/sora` |
| Body | Inter | `@fontsource-variable/inter` |
| Mono | JetBrains Mono | `@fontsource-variable/jetbrains-mono` |

### Contrast (WCAG 2.1 AA)

| Pair | Ratio | Needs | |
| --- | --- | --- | --- |
| fg on bg | 14.64:1 | 4.5:1 | pass |
| fg on bg-raised | 13.32:1 | 4.5:1 | pass |
| fg on bg-sunken | 15.40:1 | 4.5:1 | pass |
| muted on bg | 6.95:1 | 4.5:1 | pass |
| muted on bg-raised | 6.33:1 | 4.5:1 | pass |
| muted on bg-sunken | 7.32:1 | 4.5:1 | pass |
| primary on bg | 8.92:1 | 4.5:1 | pass |
| primary on bg-raised | 8.11:1 | 4.5:1 | pass |
| primary-fg on primary | 9.39:1 | 4.5:1 | pass |
| primary-fg on primary-hover | 11.05:1 | 4.5:1 | pass |
| accent on bg | 10.19:1 | 4.5:1 | pass |
| ok on bg | 9.65:1 | 4.5:1 | pass |
| warn on bg | 10.19:1 | 4.5:1 | pass |
| bad on bg | 7.87:1 | 4.5:1 | pass |
| ok on ok-bg over bg | 7.15:1 | 4.5:1 | pass |
| warn on warn-bg over bg | 7.54:1 | 4.5:1 | pass |
| bad on bad-bg over bg | 6.13:1 | 4.5:1 | pass |
| focus on bg | 10.19:1 | 3:1 | pass |

### Reproduce

- Theme file: `frontend/src/styles/themes/monterey-night.css`
- Attribute the server renders: `<html data-theme="monterey-night">`
- Select it in Wagtail: **Settings -> Site settings -> Theme**, then save.
- Preview without saving, as a website or system administrator: `https://<your-site>/?theme=monterey-night`
- Font packages: `npm install @fontsource-variable/sora @fontsource-variable/inter @fontsource-variable/jetbrains-mono`

## granite

Near-monochrome: white, near-black, grays, and one blue for links.

| Shot | File |
| --- | --- |
| Public home | `granite/site-home.png` |
| Public inner page | `granite/site-inner.png` |
| Portal dashboard | `granite/portal-dashboard.png` |
| Member profile | `granite/portal-profile.png` |
| Home at 420px | `granite/mobile-home.png` |

### Palette

| Token | Value |
| --- | --- |
| `--color-bg` | `#ffffff` |
| `--color-bg-raised` | `#fafafa` |
| `--color-bg-sunken` | `#f0f0f0` |
| `--color-fg` | `#111111` |
| `--color-primary` | `#1f1f1f` |
| `--color-primary-fg` | `#ffffff` |
| `--color-primary-hover` | `#000000` |
| `--color-accent` | `#0a58ca` |
| `--color-secondary` | `#6b7280` |
| `--color-rule` | `#e2e2e2` |
| `--color-rule-strong` | `#b1b1b1` |
| `--color-muted` | `#5c5c5c` |
| `--color-ok` | `#27693f` |
| `--color-warn` | `#825900` |
| `--color-bad` | `#ab3628` |
| `--color-focus` | `#0a58ca` |

### Fonts

| Role | Family | Package |
| --- | --- | --- |
| Display | Inter Tight | `@fontsource-variable/inter-tight` |
| Body | Inter | `@fontsource-variable/inter` |
| Mono | Geist Mono | `@fontsource-variable/geist-mono` |

### Contrast (WCAG 2.1 AA)

| Pair | Ratio | Needs | |
| --- | --- | --- | --- |
| fg on bg | 18.88:1 | 4.5:1 | pass |
| fg on bg-raised | 18.09:1 | 4.5:1 | pass |
| fg on bg-sunken | 16.57:1 | 4.5:1 | pass |
| muted on bg | 6.69:1 | 4.5:1 | pass |
| muted on bg-raised | 6.41:1 | 4.5:1 | pass |
| muted on bg-sunken | 5.87:1 | 4.5:1 | pass |
| primary on bg | 16.48:1 | 4.5:1 | pass |
| primary on bg-raised | 15.79:1 | 4.5:1 | pass |
| primary-fg on primary | 16.48:1 | 4.5:1 | pass |
| primary-fg on primary-hover | 21.00:1 | 4.5:1 | pass |
| accent on bg | 6.44:1 | 4.5:1 | pass |
| ok on bg | 6.61:1 | 4.5:1 | pass |
| warn on bg | 6.22:1 | 4.5:1 | pass |
| bad on bg | 6.38:1 | 4.5:1 | pass |
| ok on ok-bg over bg | 5.54:1 | 4.5:1 | pass |
| warn on warn-bg over bg | 5.23:1 | 4.5:1 | pass |
| bad on bad-bg over bg | 5.30:1 | 4.5:1 | pass |
| focus on bg | 6.44:1 | 3:1 | pass |

### Reproduce

- Theme file: `frontend/src/styles/themes/granite.css`
- Attribute the server renders: `<html data-theme="granite">`
- Select it in Wagtail: **Settings -> Site settings -> Theme**, then save.
- Preview without saving, as a website or system administrator: `https://<your-site>/?theme=granite`
- Font packages: `npm install @fontsource-variable/inter-tight @fontsource-variable/inter @fontsource-variable/geist-mono`

