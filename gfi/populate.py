#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import logging.config
import random
import re
from os import getenv, path
from string import Template
from urllib.parse import quote

import toml

from config import LOGGING_CONFIG
from github3 import exceptions, login
from numerize import numerize

REPO_DATA_FILE = "data/repositories.toml"
REPO_GENERATED_DATA_FILE = "data/generated.json"
GH_URL_PATTERN = re.compile(
    r"[http://|https://]?github.com/(?P<owner>[\w\.-]+)/(?P<name>[\w\.-]+)/?"
)
GOOD_FIRST_ISSUE = "good first issue"
ISSUE_LABELS = [GOOD_FIRST_ISSUE]
ISSUE_STATE = "open"
ISSUE_SORT = "created"
ISSUE_SORT_DIRECTION = "desc"
APP_KEY = getenv('TWITTER_APP_KEY')
APP_SECRET = getenv('TWITTER_APP_SECRET')
OAUTH_TOKEN = getenv('TWITTER_OAUTH_TOKEN')
OAUTH_TOKEN_SECRET = getenv('TWITTER_OAUTH_TOKEN_SECRET')
ISSUES_HTML_URL = Template("$html_url/labels/$good_first_issue")
TWEET_TEMPLATE = Template("$repo_full_name - $repo_description.\n\nLanguage: $language\nIssues: $issues_url")
ISSUE_LIMIT = 10

logging.config.dictConfig(LOGGING_CONFIG)
LOGGER = logging.getLogger(__name__)


class RepoNotFoundException(Exception):
    """Exception class for repo not found."""


def parse_github_url(url):
    """
    Take the GitHub repo URL and return a tuple with
    owner login and repo name.
    """
    match = GH_URL_PATTERN.search(url)
    if match:
        return match.groupdict()
    return {}


def get_repository_info(owner, name):
    """
    Get the relevant information needed for the repository from
    its owner login and name.
    """

    LOGGER.info("Getting info for %s/%s", owner, name)

    access_token = getenv('GITHUB_ACCESS_TOKEN')
    if not access_token:
        raise AssertionError('Access token not present in the env variable `GITHUB_ACCESS_TOKEN`')

    # create a logged in GitHub client
    client = login(token=access_token)

    info = {}

    # get the repository; if the repo is not found, raise an error
    try:
        repository = client.repository(owner, name)

        good_first_issues = list(repository.issues(
                labels=ISSUE_LABELS,
                state=ISSUE_STATE,
                number=ISSUE_LIMIT,
                sort=ISSUE_SORT,
                direction=ISSUE_SORT_DIRECTION,
        ))
        LOGGER.info('\t found %d good first issues', len(good_first_issues))
        # check if repo has at least one good first issue
        if good_first_issues:
            # store the repo info
            info["name"] = name
            info["owner"] = owner
            info["language"] = repository.language
            info["url"] = repository.html_url
            info["stars"] = repository.stargazers_count
            info["stars_display"] = numerize.numerize(repository.stargazers_count)
            info["last_modified"] = repository.last_modified
            info["id"] = str(repository.id)
            info["description"] = repository.description
            info["repo_display_name"] = repository.full_name
            info["objectID"] = str(repository.id)  # for indexing on algolia

            # get the latest issues with the tag
            issues = []
            for issue in good_first_issues:
                issues.append(
                    {
                        "title": issue.title,
                        "url": issue.html_url,
                        "number": issue.number,
                        "created_at": issue.created_at.isoformat()
                    }
                )

            info["issues"] = issues
            return info
        LOGGER.info('\t skipping the repo')
        return None
    except exceptions.NotFoundError:
        raise RepoNotFoundException()


if __name__ == "__main__":

    # parse the repositories data file and get the list of repos
    # for generating pages for.

    if not path.exists(REPO_DATA_FILE):
        raise RuntimeError("No config data file found. Exiting.")

    REPOSITORIES = []
    with open(REPO_DATA_FILE, "r") as data_file:
        DATA = toml.load(REPO_DATA_FILE)

        LOGGER.info("Found %d repository entries in %s", len(DATA["repositories"]), REPO_DATA_FILE)
        twitter = Twython(APP_KEY, APP_SECRET, OAUTH_TOKEN, OAUTH_TOKEN_SECRET)
        for repository_url in DATA["repositories"]:
            repo_dict = parse_github_url(repository_url)
            if repo_dict:
                repo_details = get_repository_info(repo_dict["owner"], repo_dict["name"])
                if repo_details:
                    REPOSITORIES.append(repo_details)
                    good_first_issues_html_url = ISSUES_HTML_URL.substitute(
                        html_url=repo_dict["url"], 
                        good_first_issue=quote(GOOD_FIRST_ISSUE)
                    )
                    tweet_string = TWEET_TEMPLATE.substitute(
                        repo_full_name=repo_dict["repo_full_name"], 
                        repo_description=repo_dict["repo_description"], 
                        language=repo_dict["language"], 
                        issues_url=good_first_issues_html_url
                    )
                    twitter.update_status(status=tweet_string)

    # shuffle the repository order
    random.shuffle(REPOSITORIES)

    # write to generated JSON file
    with open(REPO_GENERATED_DATA_FILE, 'w') as file_desc:
        json.dump(REPOSITORIES, file_desc)
    LOGGER.info("Wrote data for %d repos to %s", len(REPOSITORIES), REPO_GENERATED_DATA_FILE)
