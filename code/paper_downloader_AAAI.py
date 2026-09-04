"""paper_downloader_AAAI.py"""
import time
from bs4 import BeautifulSoup
import pickle
import os
from tqdm import tqdm
from slugify import slugify
import csv
import glob
import sys
import random
import re
import ssl
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

root_folder = os.path.abspath(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(root_folder)
from lib import csv_process
from lib.user_agents import user_agents
from lib.my_request import urlopen_with_retry


def get_aaai_driver():
    '''Create a headless Chrome driver for Cloudflare-protected AAAI pages.

    Returns:
        selenium.webdriver.Chrome: Configured Chrome driver.
    '''
    print('starting headless Chrome for AAAI proceedings pages...')
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--disable-gpu')
    try:
        chrome_install = ChromeDriverManager().install()
        chromedriver_path = os.path.join(
            os.path.dirname(chrome_install), 'chromedriver.exe')
        return webdriver.Chrome(
            service=Service(executable_path=chromedriver_path),
            options=options)
    except Exception as download_error:
        print(f'webdriver-manager unavailable: {download_error}')
        cache_pattern = os.path.expanduser(
            '~/.wdm/drivers/chromedriver/**/chromedriver.exe')
        cached_drivers = sorted(
            glob.glob(cache_pattern, recursive=True),
            key=os.path.getmtime, reverse=True)
        for chromedriver_path in cached_drivers:
            try:
                print(f'trying cached ChromeDriver: {chromedriver_path}')
                return webdriver.Chrome(
                    service=Service(executable_path=chromedriver_path),
                    options=options)
            except Exception:
                continue
        raise RuntimeError(
            'No ChromeDriver compatible with the installed Chrome was found'
        ) from download_error


def discover_aaai_track_urls(year, driver):
    '''Discover issue URLs from an AAAI annual proceedings page.

    Args:
        year (int): Four-digit AAAI conference year.
        driver (selenium.webdriver.Chrome): Active Chrome driver.

    Returns:
        dict[str, str]: Mapping from discovered issue names to URLs.

    Raises:
        ValueError: If the annual page contains no issue links.
    '''
    proceeding_number = year - 1986
    annual_url = (
        f'https://aaai.org/proceeding/aaai-{proceeding_number:02d}-{year}/')
    print(f'discovering issue URLs from {annual_url}')
    driver.get(annual_url)
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, 'main#genesis-content')))

    soup = BeautifulSoup(driver.page_source, 'html5lib')
    track_urls = {}
    for link in soup.select('main#genesis-content a[href]'):
        issue_url = link.get('href').split('#', 1)[0]
        if issue_url == annual_url:
            continue
        if not re.search(r'/proceeding/\d{2}-', issue_url):
            continue
        issue_name = slugify(link.get_text(' ', strip=True))
        track_urls[issue_name] = issue_url
        print(f'find track: {issue_name}({issue_url})')
    if not track_urls:
        raise ValueError(f'No issue URLs found on {annual_url}')
    return track_urls


def get_track_urls(year, driver=None):
    """
    get all the technical tracks urls given AAAI proceeding year
    Args:
        year (int): AAAI proceeding year, such 2023
        driver (selenium.webdriver.Chrome | None): Reusable Chrome driver for
            automatic issue discovery. Default: None.

    Returns:
        dict : All the urls of technical tracks included in
            the given AAAI proceeding. Keys are the tracks name-volume,
            and values are the corresponding urls.
    """
    # assert int(year) >= 2023, f"only support year >= 2023, but get {year}!!!"
    project_root_folder = os.path.abspath(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    dat_file_pathname = os.path.join(
        project_root_folder, 'urls', f'track_archive_url_AAAI_{year}.dat'
    )
    proceeding_th_dict = {
        1980: 1,
        1902: 2,
        1983: 3,
        1984: 4,
        1986: 5,
        1987: 6,
        1988: 7,
        1990: 8,
        1991: 9,
        1992: 10,
        1993: 11,
        1994: 12,
        1996: 13,
        1997: 14,
        1998: 15,
        1999: 16,
        2000: 17,
        2002: 18,
        2004: 19,
        2005: 20,
        2006: 21,
        2007: 22,
        2008: 23
    }
    if year >= 2022:
        owns_driver = driver is None
        if owns_driver:
            driver = get_aaai_driver()
        try:
            track_urls = discover_aaai_track_urls(year, driver)
        finally:
            if owns_driver:
                driver.quit()
        with open(dat_file_pathname, 'wb') as f:
            pickle.dump(track_urls, f)
        return track_urls

    else:
        if year >= 2010:
            proceeding_th = year - 1986
        elif year in proceeding_th_dict:
            proceeding_th = proceeding_th_dict[year]
        else:
            print(f'ERROR: AAAI proceeding was not held in year {year}!!!')
            return

        base_url = f'https://aaai.org/proceeding/aaai-{proceeding_th:02d}-{year}/'
        headers = {
            'User-Agent': user_agents[-1],
            'Host': 'aaai.org',
            'Referer': "https://aaai.org",
            'GET': base_url
        }
        if os.path.exists(dat_file_pathname):
            with open(dat_file_pathname, 'rb') as f:
                content = pickle.load(f)
        else:
            # req = urllib.request.Request(url=base_url, headers=headers)
            # content = urllib.request.urlopen(req).read()
            content = urlopen_with_retry(url=base_url, headers=headers)
            # content = open(f'..\\AAAI_{year}.html', 'rb').read()
            with open(dat_file_pathname, 'wb') as f:
                pickle.dump(content, f)
        soup = BeautifulSoup(content, 'html5lib')
        tracks = soup.find('main', {'class': 'content'}).find_all('li')
        track_urls = dict()
        for tr in tracks:
            this_track = slugify(tr.a.text)
            this_url = tr.a.get('href')
            track_urls[this_track] = this_url
            print(f'find track: {this_track}({this_url})')
    return track_urls


def get_papers_of_track_ojs(track_url):
    """
    get all the papers' title, belonging track group name and download link.
    the link should be hosted on https://ojs.aaai.org/
    Args:
        track_url (str): track url

    Returns:
        list[dict]: a list contains all the collected papers' information,
            each item in list is a dictionary, whose keys include
            ['title', 'main link', 'group']
            And the group is the specific track name.
    """
    debug = False
    paper_list = []
    headers = {
        'User-Agent': user_agents[-1],
        'Host': 'ojs.aaai.org',
        'Referer': "https://ojs.aaai.org",
        'GET': track_url
    }
    content = urlopen_with_retry(
        url=track_url, headers=headers,
        ssl_context=ssl._create_unverified_context())

    soup = BeautifulSoup(content, 'html5lib')
    tracks = soup.find('div', {'class': 'sections'}).find_all(
        'div', {'class': 'section'})
    for tr in tracks:
        this_group = slugify(tr.h2.text)
        this_paper_dict = {
            'group': this_group,
            'title': '',
            'main link': ''
        }
        papers = tr.find_all('li')
        for p in papers:
            this_paper_dict['title'] = ''
            this_paper_dict['main link'] = ''
            try:
                title = slugify(p.find('h3', {'class': 'title'}).text)
                link = p.find(
                    'a', {'class': 'obj_galley_link pdf'}
                ).get('href').replace('view', 'download')
                this_paper_dict['title'] = title
                this_paper_dict['main link'] = link
                paper_list.append(this_paper_dict.copy())
                if debug:
                    print(
                        f'paper: {title}\n\tlink:{link}\n\tgroup:{this_group}')
            except Exception as e:
                # skip unwanted target
                # print(f'ERROR: {str(e)}')
                pass
                # continue

    return paper_list


def get_papers_of_track(track_url, driver=None):
    """
    get all the papers' title, belonging track group name and download link.
    the link should be hosted on https://aaai.org/
    Args:
        track_url (str): track url
        driver (selenium.webdriver.Chrome | None): Reusable Chrome driver.
            A temporary driver is created when this is None. Default: None.

    Returns:
        list[dict]: a list contains all the collected papers' information,
            each item in list is a dictionary, whose keys include
            ['title', 'main link', 'group']
            And the group is the specific track name.
    """
    debug = False
    paper_list = []
    owns_driver = driver is None
    if owns_driver:
        driver = get_aaai_driver()
    try:
        print(f'opening AAAI proceedings page: {track_url}')
        driver.get(track_url)
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, 'main#genesis-content')))
        content = driver.page_source
    finally:
        if owns_driver:
            driver.quit()
    soup = BeautifulSoup(content, 'html5lib')
    tracks = soup.find('main', {'id': 'genesis-content'}).find_all(
        'div', {'class': 'track-wrap'})
    for tr in tracks:
        this_group = slugify(tr.h2.text)
        this_paper_dict = {
            'group': this_group,
            'title': '',
            'main link': ''
        }
        papers = tr.find_all('li')
        for p in papers:
            this_paper_dict['title'] = ''
            this_paper_dict['main link'] = ''
            try:
                title = slugify(p.find('h5').text)
                link = p.find(
                    'a', {'class': 'wp-block-button'}
                ).get('href')
                if not link.startswith('https://cdn.aaai.org/'):
                    raise ValueError(f'Unexpected non-CDN PDF URL: {link}')
                this_paper_dict['title'] = title
                this_paper_dict['main link'] = link
                paper_list.append(this_paper_dict.copy())
                if debug:
                    print(
                        f'paper: {title}\n\tlink:{link}\n\tgroup:{this_group}')
            except Exception as e:
                # skip unwanted target
                # print(f'ERROR: {str(e)}')
                pass
                # continue

    return paper_list


def save_csv(year):
    """
    write AAAI papers' urls in one csv file
    :param year: int, AAAI year, such 2019
    :return: peper_index: int, the total number of papers
    """
    project_root_folder = os.path.abspath(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    csv_file_pathname = os.path.join(
        project_root_folder, 'csv', f'AAAI_{year}.csv'
    )
    error_log = []
    paper_index = 0
    driver = get_aaai_driver() if year >= 2022 else None
    with open(csv_file_pathname, 'w', newline='') as csvfile:
        fieldnames = ['title', 'main link', 'group']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        track_urls = get_track_urls(year, driver=driver)
        for tr_name in track_urls:
            tr_url = track_urls[tr_name]
            print(f'collecting paper from {tr_name}({tr_url})')
            papers_dict_list = get_papers_of_track(tr_url, driver=driver)
            print(f'\tfind {len(papers_dict_list)} papers')
            for p in papers_dict_list:
                paper_index += 1
                writer.writerow(p)
            csvfile.flush()
            s = random.randint(3, 7)
            print(f'random sleeping {s} seconds...')
            time.sleep(s)  # avoid requesting too frequently

    if driver is not None:
        driver.quit()
        print('closed AAAI Chrome session')

    #  write error log
    print('write error log')
    log_file_pathname = os.path.join(
        project_root_folder, 'log', 'download_err_log.txt'
    )
    with open(log_file_pathname, 'w') as f:
        for log in tqdm(error_log):
            for e in log:
                if e is not None:
                    f.write(e)
                else:
                    f.write('None')
                f.write('\n')

            f.write('\n')
    return paper_index


def download_from_csv(
        year, save_dir, time_step_in_seconds=5, total_paper_number=None,
        csv_filename=None, downloader='IDM'):
    """
    download all AAAI paper given year
    :param year: int, AAAI year, such 2019
    :param save_dir: str, paper and supplement material's save path
    :param time_step_in_seconds: int, the interval time between two download
        request in seconds
    :param total_paper_number: int, the total number of papers that is going to
        download
    :param csv_filename: None or str, the csv file's name, None means to use
        default setting
    :param downloader: str or None, downloader to use. Default: 'IDM'.
    :return: True
    """
    postfix = f'AAAI_{year}'
    project_root_folder = os.path.abspath(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    csv_file_path = os.path.join(
        project_root_folder, 'csv',
        f'AAAI_{year}.csv' if csv_filename is None else csv_filename)
    csv_process.download_from_csv(
        postfix=postfix,
        save_dir=save_dir,
        csv_file_path=csv_file_path,
        is_download_supplement=False,
        time_step_in_seconds=time_step_in_seconds,
        total_paper_number=total_paper_number,
        downloader=downloader
    )


if __name__ == '__main__':
    year = 2022
    total_paper_number = 1318
    # total_paper_number = save_csv(year)
    download_from_csv(
        year,
        save_dir=fr'D:\AAAI_{year}',
        time_step_in_seconds=15,
        total_paper_number=total_paper_number)
    # for year in range(2012, 2018, 2):
    #     print(year)
    #     total_paper_number = None
    #     # total_paper_number = save_csv(year)
    #     download_from_csv(year, save_dir=f'..\\AAAI_{year}',
    #                       time_step_in_seconds=10,
    #                       total_paper_number=total_paper_number)
    #     time.sleep(2)
    # for i in range(1, 12):
    #     print(f'issue {i}/{11}')
    #     year = 2022
    #     total_paper_number = save_csv_given_urls(
    #         urls=f'https://www.aaai.org/Library/AAAI/aaai{year - 2000}-issue{i:0>2}.php',
    #         csv_filename=f'.\AAAI_{year}_issue_{i}.csv'
    #     )
    #     # total_paper_number = 156
    #     download_from_csv(
    #         year=year,
    #         csv_filename=f'.\AAAI_{year}_issue_{i}.csv',
    #         save_dir=rf'D:\AAAI_{year}',
    #         time_step_in_seconds=1,
    #         total_paper_number=total_paper_number)

    # print(get_track_urls(1980))
    # get_papers_of_track(r'https://ojs.aaai.org/index.php/AAAI/issue/view/548')

    pass
