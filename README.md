# Malicious Bot Detection
![CI](https://github.com/lerastromtsova/Malicious-Bot-Detection/actions/workflows/ci-workflow.yml/badge.svg)
![License](https://img.shields.io/github/license/lerastromtsova/Malicious-Bot-Detection)
![Open issues](https://img.shields.io/github/issues-raw/lerastromtsova/Malicious-Bot-Detection)

Detection of malicious bots spreading propaganda on Russian social media during the Russian-Ukrainian armed conflict 2022.

This project is part of the Computer Science Master's thesis at the University of Passau.

## Coding principles
Based on [Transforming Code into Scientific Contributions](https://www.frontiersin.org/articles/10.3389/fninf.2017.00069/full#:~:text=Scientific%20code%20is%20different%20from,are%20often%20overlooked%20in%20practice.). 
### Re-runnable
- [x] All dependencies and their exact versions are documented in the requirements.txt file.
- [x] The code runs in a [Docker](https://hub.docker.com/_/python/) container.

### Repeatable
- [ ] The code should be covered by tests ensuring stable repeatable results. [Hypothesis](https://hypothesis.readthedocs.io/en/latest/quickstart.html) will be used.
- [ ] The tests should be integrated into the CI pipeline. The CI pipeline is run by [Github Actions](https://docs.github.com/en/actions).

### Reproducible
- [x] All the data and code used in this project should be placed in this repository for easy future distribution.

### Reusable
- [ ] The code should contain sufficient comments and documentation in order to be reusable. [Docstring](https://peps.python.org/pep-0257/) and [Sphinx](https://www.sphinx-doc.org/en/master/) are used to generate the documentation.
- [x] Type hinting is to be used throughout the code for clarity.

### Replicable
1. A clear description of the algorithms used should be publicly available.

## Flowchart
```mermaid
flowchart TB
    voynaSlov[(VoynaSlov repository files)]
    parser[Data parsing component]
    vk[Vkontakte API]
    database[(Database)]
    model1[Warped correlation finder]
    model2[Graph-based approach]
    model3[CatchSync]
    model4[Network-based framework]
    model5[Heterogenity-aware bot detection model]
    combined[Combined model]
    webInterface[Web interface]
    
    subgraph dataCollection
    voynaSlov--Comment IDs-->parser
    vk--Comments-->parser
    parser--Store data-->database
    end
    subgraph training
    database--Retrieve data-->model1 & model2 & model3 & model4 & model5 
    model1--Train on data-->model1
    model2--Train on data-->model2
    model3--Train on data-->model3
    model4--Train on data-->model4
    model5--Train on data-->model5
    end
    subgraph predicting
    webInterface--Input user ID-->training
    training--Make predictions-->combined
    combined--Make final prediction-->webInterface
    end
```

## How to set up the project

### Environment variables

Place an `.env` file in the root folder of the project and insert the following values:
```
COMMENT_ID_SOURCE_REPO=chan0park/VoynaSlov
GITHUB_ACCESS_TOKEN=...
LOG_LEVEL=INFO
VK_API_TOKEN=...
MONGO_DB_PASSWORD=...
WEB_SECRET=...
```

### Docker
```commandline
docker build -t bot-detection .
docker run bot-detection
```

### Babel
```commandline
pybabel extract -F babel.cfg -o messages.pot templates/index.html
pybabel init -i messages.pot -d translations -l ru 
pybabel compile -d translations
```
