#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Apr 28 08:57:38 2018

@author: me
"""

import BeautifulSoup
import urllib

        
def FieldCleaner(FieldString):
    while '\n' in FieldString:
        FieldString = FieldString.replace('\n','')
    FieldString = FieldString.strip(':')
    FieldString = FieldString.strip()
    return FieldString
        
def FieldValueCleaner(FieldValueString):        
    return FieldCleaner(FieldValueString)

def FieldNameCleaner(FieldNameString):
    return FieldCleaner(FieldNameString).lower()

def alternate_address(FieldStr):
    FieldStr = FieldValueCleaner(FieldStr)
    return FieldStr.replace('Show fewer','')

def no_more_info(FieldStr):
    FieldStr = FieldValueCleaner(FieldStr)
    return FieldStr.replace('(More Info)','').strip()
    
def roll_out_cart(FieldStr):
    FieldStr = FieldValueCleaner(FieldStr)
    return FieldStr.replace('(Holiday Schedule)','')

def extract_number(fieldValue):
    fieldValue = FieldValueCleaner(fieldValue)
    fieldNumbers = [int(s) for s in fieldValue.split() if s.isdigit()]
    return fieldNumbers[0]

def housing_conservation_dist(FieldStr):
    return extract_number(FieldStr.replace('.',' '))

def dollars_to_numbers(FieldStr):
    FieldStr = FieldValueCleaner(FieldStr)
    FieldStr = FieldStr.strip('$')
    FieldStr = FieldStr.replace(',','')
    return FieldStr

#dictionary of field names whose values require special cleaning functions
SpecialCleaning = {'alternate address':alternate_address,
                   'empowerment zone':no_more_info,
                   'hubzone':no_more_info,
                   'roll out cart':roll_out_cart,
                   'urban enterprise loan area':no_more_info,
                   'housing conservation dist.':housing_conservation_dist,
                   'appraised total':dollars_to_numbers,
                   'assessed improvements':dollars_to_numbers,
                   'assessed land':dollars_to_numbers,
                   'assessed total':dollars_to_numbers,}

#fields we can ignore (just contain contact information)
fieldsToRemove = ['ameren','laclede gas','msd','water']

#fields we want to extract numbers from
codes = ['ward','police district','neighborhood','fire district']

def parse_page(page):
    soup = BeautifulSoup(page, "lxml")
    tables = soup.find_all('table', class_='data vertical-table striped')
    info = dict()
    # table_body = table.find('tbody')
    for table in tables:
        for row in table.findAll('tr'):
            cells = row.findAll('td')
            states = row.findAll('th')
            if len(states)==0 or len(cells)==0:
                continue #no data under this heading
            FieldName = states[0].find(text=True)
            FieldValue = ''.join(cells[0].find_all(text=True))
            if not FieldValue: #nothing to see here folks
                continue 
        
            FieldName = FieldNameCleaner(FieldName)
            if FieldName in fieldsToRemove:
                continue #ignore these fields
            elif FieldName in SpecialCleaning.keys(): #these have special value cleaning functions
                FieldValue = SpecialCleaning[FieldName](FieldValue)
            else: #apply generic field value cleaner
                FieldValue = FieldValueCleaner(FieldValue)
                
            info[FieldName] = FieldValue
                
            #encode fields and add a new field to dictionary for which we just want numbers
            if FieldName in codes:
                FieldValue_enc = extract_number(FieldValue)
                info[FieldName+' num'] = FieldValue_enc
            
    return info
    
def get_page(parcel_id):
    while len(parcel_id)<=10:
        parcel_id = '0'+parcel_id
    url = 'https://www.stlouis-mo.gov/data/address-search/index.cfm?parcelid={}'\
            '&firstview=true&categoryBy=form.start,form.RealEstatePropertyInfor,'\
            'form.BoundaryGeography,form.ResidentialServices,form.TrashMaintenance,'\
            'form.ElectedOfficialsContacts,form.RealEstatePropertyInfor,'\
            'form.BoundaryGeography,form.TrashMaintenance,'\
            'form.ElectedOfficialsContacts'.format(parcel_id)    
    return urllib.request.urlopen(url)


def process_row(row):
    pid = str(row.parcel_id)
    page = get_page(pid)
    data = parse_page(page)
    return {pid:data}





