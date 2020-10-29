<!--
*** Thanks for checking out this README Template. If you have a suggestion that would
*** make this better, please fork the repo and create a pull request or simply open
*** an issue with the tag "enhancement".
*** Thanks again! Now go create something AMAZING! :D
***
***
***
*** To avoid retyping too much info. Do a search and replace for the following:
*** github_username, repo_name, twitter_handle, email
-->


<!-- PROJECT SHIELDS -->
<!--
*** I'm using markdown "reference style" links for readability.
*** Reference links are enclosed in brackets [ ] instead of parentheses ( ).
*** See the bottom of this document for the declaration of the reference variables
*** for contributors-url, forks-url, etc. This is an optional, concise syntax you may use.
*** https://www.markdownguide.org/basic-syntax/#reference-style-links
-->

<!-- PROJECT LOGO -->
<br />
<p align="center">
  <a href="https://github.com/github_username/repo_name">
    <img src="images/logo.png" alt="Logo" width="450" height="240">
  </a>

  <h3 align="center">Messenger Analyzer</h3>

  <p align="center">
    An analyzer of messages
    <br />
    <a href="https://github.com/ShadehaterCS/TheMessengerProject/issues">Report Bug</a>
    ·
    <a href="https://github.com/ShadehaterCS/TheMessengerProject/issues">Request Feature</a>
  </p>
</p>



<!-- TABLE OF CONTENTS -->
## Table of Contents

* [About the Project](#about-the-project)
  * [Built With](#built-with)
* [Getting Started](#getting-started)
  * [Prerequisites](#prerequisites)
  * [Installation](#installation)
* [Usage](#usage)
* [Roadmap](#roadmap)
* [Contributing](#contributing)
* [License](#license)
* [Example Visualization](#example-visualization)


<!-- ABOUT THE PROJECT -->
## About The Project
**An analysis & plotting tool**  
**This software does NOT use networking of any kind**  
![example.gif](https://media.giphy.com/media/16nTbGPdl2bHO08okk/giphy.gif)
### Built With

* []()Python 3
* []()matplotlib
* []()NumPy

<!-- GETTING STARTED -->
## Getting Started

To get a local copy up and running follow these simple steps.

### Prerequisites
List:
* Python 3
* matplotlib
```sh
python -m pip install -U matplotlib
```
* NumPy
```sh
python -m pip install -U numpy
```
* Your FB data
```sh
see instructions below
```

### Installation

1. Clone the repo
```sh
git clone https://github.com/github_username/repo_name.git
```
2. Install pip packages
```sh
pip install -r requirements.txt
```

<!-- USAGE EXAMPLES -->
## Usage

You can use these scripts for structuring, extracting and visualizing your data taken from Facebook's Messenger.  

It is **indifferent** as to how many people there are in a conversation, the plots and DS will work regardless.  

The main use of this tool is to **plot** your data.  

To do that, all you need to do is run main.py, input the folder's name where the JSON files are and you'll be presented with the oh so faithful press 1-5 menu.  

## Guide
**First of all** you'll need to download your data through Facebook. Now, Facebook allow to download only your messages but it's a small process. For more info on how to do that visit the link below
* []() https://www.facebook.com/help/1701730696756992?helpref=hc_global_nav  
**OR**  
* []() *facebook.com -> Settings & Privacy -> Settings -> Your Facebook Information -> Access Your Information -> (top of page) download your information*  
**OR**
* []() *https://facebook.com/dyi  
* []() *Deselect* them all and then select only your Messages if that's all you want.
* []() Make sure you choose download data as **JSON**
* []() **Data Range**: All of my Data | **Format:** JSON | **Media Quality:** that's up to you
**Congratulations, you now have your data**  
* []() Inside your downloaded .zip you'll see the folders you selected. We're interested in the messages one. Apparently the folders are named with fb username + a random uid.
* []() Inside every folder you'll see one or more JSON files. Copy that folder and be ready to rename it because you can't be typing that whole thing.  

**Now go into the repo's folder**
* []()You'll see that there is a folder named MessagesSources.  
That's the folder the script is going to look into to find the folders containing your JSON files for every specific conversation.  
Move your extracted folders inside that one and name it appropriately so there's no confusion for you.  

**Now you can start**
Open the folder in your preferred editor (I'd suggest VSCode) or simply open terminal / cmd in the repo's folder  
* []() Run *python main.py*  
* []() Input your folder's name
* []() The menu will pop up, you can use the available options through your keyboard 1-5 keys
* []() Success  
<!-- ROADMAP -->
## Roadmap

As per v1 this codebase only supports Facebook's Messenger files and structure.  
Some functionality for instagram's messaging will be added.


<!-- CONTRIBUTING -->
## Contributing

Contributions are what make the open source community such an amazing place to be learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request



<!-- LICENSE -->
## License

Distributed under the MIT License. See `LICENSE` for more information.

<!-- EXAMPLE -->
## Example Visualization
![visualization.jpg](https://i.imgur.com/LMWYI8R.jpg)

<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[issues-url]: https://github.com/ShadehaterCS/MessengerAnalyzer/issues
[license-url]: https://github.com/ShadehaterCS/MessengerAnalyzer/blob/master/LICENSE.txt
