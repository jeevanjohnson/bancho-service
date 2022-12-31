from datetime import datetime

import pytz

import constants


def country_code_from_utc_offset(utc_offset: int) -> str:
    for time_zone in pytz.all_timezones:
        tz = pytz.timezone(time_zone)

        offset = tz.utcoffset(datetime.now()).total_seconds() / 3600

        if offset == utc_offset:
            if tz.zone not in constants.time.time_zone_to_country_code:
                continue

            country_code = constants.time.time_zone_to_country_code[tz.zone].lower()

            if country_code not in constants.time.country_codes_to_osu_code:
                continue
            else:
                return country_code

    return "xx"


def country_code_to_client_code(country_code: str) -> int:
    return constants.time.country_codes_to_osu_code[country_code]
