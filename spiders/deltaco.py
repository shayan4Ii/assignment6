import scrapy
from scrapy import Request
from scrapy.http import Response
import json
import html
from json.decoder import JSONDecoder
from datetime import datetime

class DeltacoSpider(scrapy.Spider):
    name = "deltaco"
    allowed_domains = ["locations.deltaco.com"]
    start_urls = ["https://locations.deltaco.com/us"]

    def parse(self, response):
        states = response.xpath('//div[contains(@class, "city-name col-6 col-sm-4 col-md-3 col-lg-2")]/a/@href').getall()
        yield from response.follow_all(states, self.parse_states)
        
    def parse_states(self, response: Response):
        cities = response.xpath('//div[contains(@class, "city-name")]/a/@href').getall()
        yield from response.follow_all(cities, self.parse_city)
        
    def parse_city(self, response: Response):
        stores = response.xpath('//div[contains(@class, "col-12 col-sm-6 col-md-4 col-lg-3 gtm-store")]//a[contains(@class, "name")]/@href').getall()
        yield from response.follow_all(stores, self.parse_stores)
        
    def geo_data(self,response: Response):
        loc_dict = {}
        script_data = response.xpath('(//script[@type="application/ld+json"])/text()').get()
        script_data = script_data.strip()
        decoder = JSONDecoder()
        if script_data:
            geo_data, idx = decoder.raw_decode(script_data)
        else:
            self.logger.info("No Geo Data!")
        loc_dict = {
            "type" : "Point",
            "coordinates" : [
                float(geo_data['geo']['latitude']),
                float(geo_data['geo']['longitude'])
            ]
        }
        return loc_dict

    def get_hours(self, response: Response):
        hours_dict = {}
        raw_time = response.xpath('(//script[@type="application/ld+json"])/text()').get()
        raw_time = raw_time.strip()
        decoder = JSONDecoder()
        if raw_time:
            hour_data,idx = decoder.raw_decode(raw_time)
            days = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
            open_hours = hour_data.get("openingHoursSpecification", [])
            for day in open_hours:
                week_day = day.get("dayOfWeek", "").split("/")[-1].lower()
                open_time = day.get("opens", "").replace(".","").lower()
                close_time = day.get("closes", "").replace(".","").lower()
                if week_day in days:
                    if "open 24hs" in open_time or "open 24hs" in close_time:
                        hours_dict[week_day] = {
                            "open" : "12:00am",
                            "close" : "11:59pm"
                        }
                    else:
                        hours_dict[week_day] = {
                            "open" : open_time,
                            "close" : close_time
                        }
        return hours_dict
    def raw_data(self, response: Response):
        raw = response.xpath('(//script[@type="application/ld+json"])/text()').get()
        raw = raw.strip()
        decoder = JSONDecoder()
        if raw:
            raw_d = decoder.raw_decode(raw)
        return raw_d
        

    def parse_stores(self, response: Response):
        address = response.xpath('//div[contains(@class, "address")]/text()').get().strip()
        address2 = response.xpath('//div[contains(@class, "address")]/span/text()').get().strip()
        name = response.xpath('//div[contains(@class, "col-12")]/h1/text()').get().strip()
        
        if not name:
            name = response.xpath('//div[@class="col-12"]/h1[@class="text-left"]/text()[normalize-space()]').get().strip()
        loc_dict = self.geo_data(response)
        hours_dict = self.get_hours(response)
        raw_d = self.raw_data(response)
        yield{
            'number' : response.xpath("//script[contains(text(), 'dimensionLocationNumber')]/text()").re_first(r"(?:dimensionLocationNumber\'\:\s\')(.*?)(?:\')"),
            'name' : name,
            'address' : f"{address}, {address2}",
            'phone_number' : response.xpath('//div[contains(@class, "tel")]/a/text()').get().strip(),
            'url' : response.url,
            'location' : loc_dict,
            'hours' : hours_dict,
            'coming_soon' : bool(response.xpath("//span[@class='comingSoon']")),
            'url': response.url,
            'raw' : raw_d
        }
