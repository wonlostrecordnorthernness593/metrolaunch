## MetroLaunch
A nicely-featured third party home screen for iOS in the style of Microsoft's old MetroUI... Built as a PWA, free forever, smooth animations, runnable offline, and hassle free updates. Uses the original Windows 8 weather images :)

![screenshot-a](https://i.ibb.co/9HNxBPN0/IMG-3137.png)

**How to make it easier then clicking on the icon on the NORMAL homescreen every time** - Make a shortcut to open the URL of the webapp, which is listed in this repo. In order for this to work, you must have the app installed via the 'add to home screen option' already. Then set it as the double back tap option.

Also, not many iOS users know, but to swipe between apps, you can just swipe left or right on the navigation bar!!

Please fully read the readme before installing and using the launcher...

## This app relies on URL schemes to launch and add apps...

**What is a URL Scheme** - URL schema are links that are able to reference other apps installed on your device. Both Android and iOS have them, but Android launchers don't usually ever need to rely on them

**So why do we have to** - Apple in their infinite wisdom has disallowed enumerating other apps on the device and opening them 'just because' and usually requires some sort of intent. Hence, a weather app may have a scheme like `weather-app-best://getforloc=milwaukee` - Note that that is a pretty crude example but the point is the same. Thanfully, opening an app with nothing in the url scheme usally works just fine. For example `netflix://` will just open Netflix

**How can I get them** - Sometimes you get lucky and it is just the app name with a `://` after it. Other times it is the Bundle ID. Or sometimes, it's completely random gibberish. For example, the url scheme for the app 'What The Forecast' is `fb1682603758661443://` so sometimes it is very hard to find them. Oftentimes there is lists online for them, but they usually don't have all the apps you'd want

## Ways to get them easier then guessing

**Download the theming app 'Brass'** - after which you can add apps to the home screen with it through a configuration profile and hold them on the home screen, press share, then copy link. But sometimes you may notice it will still be blank!! Which means that the app has no URL scheme. But don't panic, there is still a way that will work with all apps.

**Shortcuts method** - simply make a shortcut in the Apple Shortcuts app to open an app, and name it something simple like 'SC1' or 'SC2' then, in the launcher, you can use the scheme `shortcuts://run-shortcut?name=[name]` and there will be no app this won't work with.

## Spotify integration

You need a Mac running python3 for this server part. This is because spotify is currently being a douche after a certain shadow library dumped all of their content and has halted new API regsitrations. I am looking for a better way around this but don't hold your breath. Just make sure you put your free [Discogs](https://www.discogs.com/) API key in the conifg section of the python file and have the Spotify app running on your mac. Then in the Spotify live tile's settings, configure the server IP and port. You may want to use something like [Tailscale](https://tailscale.com/) so you'll always be able to access it.

I am working on making a Windows and Linux server version...

## Using the app

You will need an [OpenWeatherMap](https://openweathermap.org/) API key if you want the weather tile to work. The app will tell you how to do it. \
To access the menu to add an app or go to the settings, press the vertical elipses menu in the status bar, and chose your option from there.

To update the app, go the the settings cache section, then press update. Thanks for cheking this out everybody :)
