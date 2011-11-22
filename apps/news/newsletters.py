
NEWSLETTERS = {
    'mozilla-and-you': 'MOZILLA_AND_YOU',
    'mobile': 'ABOUT_MOBILE',
    'beta': 'FIREFOX_BETA_NEWS',
    'aurora': 'AURORA',
    'about-mozilla': 'ABOUT_MOZILLA',
    'drumbeat': 'DRUMBEAT_NEWS_GROUP',
    'addons': 'ABOUT_ADDONS',
    'hacks': 'ABOUT_HACKS',
    'labs': 'ABOUT_LABS',
    'qa-news': 'QA_NEWS',
    'student-reps': 'STUDENT_REPS',
    'about-standards': 'ABOUT_STANDARDS',
    'mobile-addon-dev': 'MOBILE_ADDON_DEV',
    'addon-dev': 'ADD_ONS',
    'join-mozilla': 'JOIN_MOZILLA',
    'mozilla-phone': 'MOZILLA_PHONE',
    'app-dev': 'APP_DEV'
}

NEWSLETTER_NAMES = NEWSLETTERS.keys()
NEWSLETTER_FIELDS = NEWSLETTERS.values()


def newsletter_field(name):
    return NEWSLETTERS.get(name, False)


def newsletter_name(field):
    i = NEWSLETTER_FIELDS.index(field)
    return NEWSLETTER_NAMES[i]

