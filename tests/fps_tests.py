import unittest
import sys
from jsonschema import ValidationError
from publicsuffix2 import PublicSuffixList
from unittest import mock
from requests import structures

sys.path.append('../first-party-sets')
from FpsSet import FpsSet
from FpsCheck import FpsCheck
from check_sites import find_diff_sets

class TestValidateSchema(unittest.TestCase):
    """A test suite for the validate_schema function of FpsCheck"""

    def test_no_primary(self):
        json_dict = {
            "sets":
            [
                {
                    "contact": "abc@example.com",
                    "associatedSites": ["https://associated1.com"],
                    "serviceSites": ["https://service1.com"],
                    "rationaleBySite": {
                        "https://associated1.com": "example rationale",
                        "https://service1.com": "example rationale",
                    },
                    "ccTLDs": {
                        "https://associated1.com": ["https://associated1.ca"]
                    }
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                      etlds=None, icanns=set(['ca']))
        with self.assertRaises(ValidationError):
            fp.validate_schema("SCHEMA.json")

    def test_no_rationaleBySite(self):
        json_dict = {
            "sets":
            [
                {
                    "contact": "abc@example.com",
                    "primary": "https://primary1.com",
                    "associatedSites": ["https://associated1.com"],
                    "serviceSites": ["https://service1.com"],
                    "ccTLDs": {
                        "https://associated1.com": ["https://associated1.ca"]
                    }
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                      etlds=None, icanns=set(['ca']))
        with self.assertRaises(ValidationError):
            fp.validate_schema("SCHEMA.json")

    def test_invalid_field_type(self):
        json_dict = {
            "sets":
            [
                {
                    "contact": "abc@example.com",
                    "primary": "https://primary.com",
                    "ccTLDs": {
                        "https://primary.com": "https://primary.ca"
                    }
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                      etlds=None, icanns=set(['ca']))
        with self.assertRaises(ValidationError):
            fp.validate_schema("SCHEMA.json")

    def test_no_contact(self):
       json_dict = {
            "sets":
            [
                {
                    "primary": "https://primary.com",
                    "associatedSites": ["https://associated1.com"],
                    "serviceSites": ["https://service1.com"],
                    "rationaleBySite": {
                        "https://associated1.com": "example rationale",
                        "https://service1.com": "example rationale",
                    },
                    "ccTLDs": {
                        "https://associated1.com": ["https://associated1.ca"]
                    }
                }
            ]
        }
       fp = FpsCheck(fps_sites=json_dict,
                      etlds=None, icanns=set(['ca']))
       with self.assertRaises(ValidationError):
            fp.validate_schema("SCHEMA.json")

class TestFpsSetEqual(unittest.TestCase):
    def test_equal_case(self):
        fps_1 = FpsSet(ccTLDs={
                        "https://primary.com": ["https://primary.ca"]
                    }, 
                    primary="https://primary.com")
        fps_2 = FpsSet(ccTLDs={
                        "https://primary.com": ["https://primary.ca"]
                    }, 
                    primary="https://primary.com")
        self.assertIsNot(fps_1, fps_2)
        self.assertEqual(fps_1, fps_2)
        self.assertEqual(fps_1, fps_1)

    def test_inequal_cases(self):
        fps_1 = FpsSet(ccTLDs={
                        "https://primary.com": ["https://primary.ca"]
                    }, 
                    primary="https://primary.com")
        fps_2 = FpsSet(ccTLDs={
                        "https://primary.com": ["https://primary.co.uk"]
                    }, 
                    primary="https://primary.com")
        self.assertNotEqual(fps_1, fps_2)

        fps_2.ccTLDs = {"https://primary.com": ["https://primary.ca"]}
        self.assertEqual(fps_1, fps_2)

        fps_1.associated_sites = ["https://associated1.com"]
        fps_2.associated_sites = ["https://associated2.com"]
        self.assertNotEqual(fps_1, fps_2)

        fps_2.associated_sites = ["https://associated1.com"]
        self.assertEqual(fps_1, fps_2)

        fps_1.service_sites = ["https://service1.com"]
        fps_2.service_sites = ["https://service2.com"]
        self.assertNotEqual(fps_1, fps_2)

class TestFpsIncludes(unittest.TestCase):
    def test_primary_case(self):
        fps = FpsSet(ccTLDs={
                        "https://primary.com": ["https://primary.ca"]
                    }, 
                    primary="https://primary.com")
        self.assertTrue(fps.includes("https://primary.com"))
        self.assertFalse(fps.includes("https://primary2.com"))

    def test_associated_case(self):
        fps = FpsSet(
                    ccTLDs={},
                    primary="https://primary.com",
                    associated_sites= ["https://associated1.com", "https://associated2.com"])
        self.assertTrue(fps.includes("https://associated1.com"))
        self.assertTrue(fps.includes("https://associated2.com"))
        self.assertFalse(fps.includes("https://associated3.com"))
    
    def test_cctld_case(self):
        fps = FpsSet(ccTLDs={
                        "https://primary.com": ["https://primary.ca", "https://primary.co.uk"]
                    }, 
                    primary="https://primary.com")

        self.assertTrue(fps.includes("https://primary.ca"))
        self.assertFalse(fps.includes("https://primary.ca", with_ccTLDs=False))
        

class TestLoadSets(unittest.TestCase):
    def test_collision_case(self):
        json_dict = {
            "sets":
            [
                {
                    "primary": "https://primary.com",
                    "ccTLDs": {
                        "https://primary.com": ["https://primary.ca"]
                    }
                },
                {
                    "primary": "https://primary.com",
                    "ccTLDs": {
                        "https://primary.com": ["https://primary.co.uk"]
                    }
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                      etlds=None,
                       icanns=set(['ca', 'co.uk']))
        loaded_sets = fp.load_sets()
        expected_sets = {
            'https://primary.com': FpsSet(ccTLDs={
                        "https://primary.com": ["https://primary.ca"]
                    }, 
                    primary="https://primary.com")
        }
        self.assertEqual(loaded_sets, expected_sets)
        self.assertEqual(fp.error_list, 
        ["https://primary.com is already a primary of another site"])
    
    def test_expected_case(self):
        json_dict = {
            "sets":
            [
                {
                    "primary": "https://primary.com",
                    "ccTLDs": {
                        "https://primary.com": ["https://primary.ca"]
                    }
                },
                {
                    "primary": "https://primary2.com",
                    "ccTLDs": {
                        "https://primary2.com": ["https://primary2.co.uk"]
                    }
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                      etlds=None,
                       icanns=set(['ca', 'co.uk']))
        loaded_sets = fp.load_sets()
        expected_sets = {
            'https://primary.com': FpsSet(ccTLDs={
                        "https://primary.com": ["https://primary.ca"]
                    }, 
                    primary="https://primary.com"),
            'https://primary2.com': FpsSet(ccTLDs={
                        "https://primary2.com": ["https://primary2.co.uk"]
                    }, 
                    primary="https://primary2.com")
        }
        self.assertEqual(loaded_sets, expected_sets)
        self.assertEqual(fp.error_list, [])

class TestHasRationales(unittest.TestCase):
    def test_no_rationales(self):
        json_dict = {
            "sets":
            [
                {
                    "primary": "https://primary.com",
                    "associatedSites": ["https://associated1.com"],
                    "serviceSites": ["https://service1.com"],
                    "rationaleBySite": {}
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                      etlds=None,
                       icanns=set())
        loaded_sets = fp.load_sets()
        fp.has_all_rationales(loaded_sets)
        self.assertEqual(fp.error_list, 
        ["There is no provided rationale for https://associated1.com", 
        "There is no provided rationale for https://service1.com"])
    
    def test_expected_rationales_case(self):
        json_dict = {
            "sets":
            [
                {
                    "primary": "https://primary.com",
                    "associatedSites": ["https://associated1.com"],
                    "serviceSites": ["https://service1.com"],
                    "rationaleBySite": {
                        "https://associated1.com": "example rationale",
                        "https://service1.com": "example rationale",
                    },
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                      etlds=None,
                       icanns=set())
        loaded_sets = fp.load_sets()
        self.assertEqual(fp.error_list, [])  

class TestCheckExclusivity(unittest.TestCase):
    def test_servicesets_overlap(self):
        json_dict = {
            "sets":
            [
                {
                    "primary": "https://primary.com",
                    "associatedSites": ["https://associated1.com"],
                    "serviceSites": ["https://service1.com"],
                    "rationaleBySite": {}
                },
                {
                    "primary": "https://primary2.com",
                    "associatedSites": ["https://associated2.com"],
                    "serviceSites": ["https://service1.com"],
                    "rationaleBySite": {}
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                      etlds=None,
                       icanns=set())
        loaded_sets = fp.load_sets()
        fp.check_exclusivity(loaded_sets)
        self.assertEqual(fp.error_list, 
         ["These service sites are already registered in another"
                        + " first party set: {'https://service1.com'}"])

    def test_primary_is_associate(self):
        json_dict = {
            "sets":
            [
                {
                    "primary": "https://primary.com",
                    "associatedSites": ["https://primary2.com"],
                    "serviceSites": ["https://service1.com"],
                    "rationaleBySite": {}
                },
                {
                    "primary": "https://primary2.com",
                    "associatedSites": ["https://associated2.com"],
                    "serviceSites": ["https://service2.com"],
                    "rationaleBySite": {}
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                      etlds=None,
                       icanns=set())
        loaded_sets = fp.load_sets()
        fp.check_exclusivity(loaded_sets)
        self.assertEqual(fp.error_list, 
         ["This primary is already registered in another"
                        + " first party set: https://primary2.com"])
                
    def test_expected_case(self):
        json_dict = {
            "sets":
            [
                {
                    "primary": "https://primary.com",
                    "associatedSites": ["https://associated1.com"],
                    "serviceSites": ["https://service1.com"],
                    "rationaleBySite": {}
                },
                {
                    "primary": "https://primary2.com",
                    "associatedSites": ["https://associated2.com"],
                    "serviceSites": ["https://service2.com"],
                    "rationaleBySite": {}
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                      etlds=None,
                       icanns=set())
        loaded_sets = fp.load_sets()
        fp.check_exclusivity(loaded_sets)
        self.assertEqual(fp.error_list, [])
    
class TestFindNonHttps(unittest.TestCase):
    def test_no_https_in_primary(self):
        json_dict = {
            "sets":
            [
                {
                    "primary": "primary.com",
                    "associatedSites": ["https://associated1.com"],
                    "serviceSites": ["https://service1.com"],
                    "rationaleBySite": {}
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                      etlds=None,
                       icanns=set())
        loaded_sets = fp.load_sets()
        fp.find_non_https_urls(loaded_sets)
        self.assertEqual(fp.error_list, 
         ["The provided primary site does not begin with https:// " +
         "primary.com"])
                
    def test_no_https_in_ccTLD(self):
        json_dict = {
            "sets":
            [
                {
                    "primary": "https://primary.com",
                    "associatedSites": ["https://associated1.com"],
                    "serviceSites": ["https://service1.com"],
                    "ccTLDs": {
                        "https://primary.com": ["primary.ca"]
                    },
                    "rationaleBySite": {}
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                      etlds=None,
                       icanns=set())
        loaded_sets = fp.load_sets()
        fp.find_non_https_urls(loaded_sets)
        self.assertEqual(fp.error_list, 
         ["The provided alias site does not begin with" +
                                " https:// primary.ca"])
                
    def test_multi_no_https(self):
        json_dict = {
            "sets":
            [
                {
                    "primary": "primary.com",
                    "associatedSites": ["associated1.com"],
                    "serviceSites": ["service1.com"],
                    "ccTLDs": {
                        "primary.com": ["primary.ca"]
                    },
                    "rationaleBySite": {}
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                      etlds=None,
                       icanns=set())
        loaded_sets = fp.load_sets()
        fp.find_non_https_urls(loaded_sets)
        self.assertEqual(fp.error_list, 
         [
        "The provided primary site does not begin with https:// primary.com", 
        "The provided alias does not begin with https:// primary.com",
        "The provided alias site does not begin with https:// primary.ca",
        "The provided associated site does not begin with https:// " + 
        "associated1.com",
        "The provided service site does not begin with https:// service1.com"
         ])
        
class TestFindInvalidETLD(unittest.TestCase):
    def test_invalid_etld_primary(self):
        json_dict = {
            "sets":
            [
                {
                    "primary": "https://primary.c2om",
                    "associatedSites": ["https://associated1.com"],
                    "serviceSites": ["https://service1.com"],
                    "rationaleBySite": {}
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                     etlds=PublicSuffixList(
                        psl_file = 'effective_tld_names.dat'),
                     icanns=set())
        loaded_sets = fp.load_sets()
        fp.find_invalid_eTLD_Plus1(loaded_sets)
        self.assertEqual(fp.error_list, 
         ["The provided primary site is not an eTLD+1: https://primary.c2om"])
                
    def test_invalid_etld_cctld(self):
        json_dict = {
            "sets":
            [
                {
                    "primary": "https://primary.com",
                    "associatedSites": ["https://associated1.com"],
                    "serviceSites": ["https://service1.com"],
                    "ccTLDs": {
                        "https://primary.com": ["https://primary.c2om"]
                    },
                    "rationaleBySite": {}
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                     etlds=PublicSuffixList(
                        psl_file = 'effective_tld_names.dat'),
                     icanns=set())
        loaded_sets = fp.load_sets()
        fp.find_invalid_eTLD_Plus1(loaded_sets)
        self.assertEqual(fp.error_list, 
         ["The provided aliased site is not an eTLD+1: https://primary.c2om"])
                
    def test_multi_invalid_etlds(self):
        json_dict = {
            "sets":
            [
                {
                    "primary": "https://primary.c2om",
                    "associatedSites": ["https://associated1.c2om"],
                    "serviceSites": ["https://service1.c2om"],
                    "ccTLDs": {
                        "https://primary.c2om": ["https://primary.c2om"]
                    },
                    "rationaleBySite": {}
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                     etlds=PublicSuffixList(
                        psl_file = 'effective_tld_names.dat'),
                     icanns=set())
        loaded_sets = fp.load_sets()
        fp.find_invalid_eTLD_Plus1(loaded_sets)
        self.assertEqual(fp.error_list, 
         ["The provided primary site is not an eTLD+1: https://primary.c2om",
          "The provided alias is not an eTLD+1: https://primary.c2om",
          "The provided aliased site is not an eTLD+1: https://primary.c2om",
          "The provided associated site is not an eTLD+1: https://associated1.c2om",
          "The provided service site is not an eTLD+1: https://service1.c2om"])
        
    def test_not_etld_plus1(self):
        json_dict = {
            "sets":
            [
                {
                    "primary": "https://subdomain.primary.com",
                    "ccTLDs": {},
                    "rationaleBySite": {}
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                     etlds=PublicSuffixList(
                        psl_file = 'effective_tld_names.dat'),
                     icanns=set())
        loaded_sets = fp.load_sets()
        fp.find_invalid_eTLD_Plus1(loaded_sets)
        self.assertEqual(fp.error_list, 
                         ["The provided primary site is not an eTLD+1: https://subdomain.primary.com"])
        
    def test_valid_etld_plus1(self):
        json_dict = {
            "sets":
            [
                {
                    "primary": "https://primary.com.ar",
                    "ccTLDs": {},
                    "rationaleBySite": {}
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                     etlds=PublicSuffixList(
                        psl_file = 'effective_tld_names.dat'),
                     icanns=set())
        loaded_sets = fp.load_sets()
        fp.find_invalid_eTLD_Plus1(loaded_sets)
        self.assertEqual(fp.error_list, 
                         [])
    
    def test_valid_tld_plus1(self):
        json_dict = {
            "sets":
            [
                {
                    "primary": "https://primary.com",
                    "ccTLDs": {},
                    "rationaleBySite": {}
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                     etlds=PublicSuffixList(
                        psl_file = 'effective_tld_names.dat'),
                     icanns=set())
        loaded_sets = fp.load_sets()
        fp.find_invalid_eTLD_Plus1(loaded_sets)
        self.assertEqual(fp.error_list, 
                         [])
        
    def test_just_suffix(self):
        json_dict = {
            "sets":
            [
                {
                    "primary": "https://7.bg",
                    "rationaleBySite": {}
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                    etlds=PublicSuffixList(
                        psl_file = 'effective_tld_names.dat'),
                    icanns=set())
        loaded_sets = fp.load_sets()
        fp.find_invalid_eTLD_Plus1(loaded_sets)
        self.assertEqual(fp.error_list, 
                ["The provided primary site is not an eTLD+1: https://7.bg"])
        
class TestFindInvalidESLDs(unittest.TestCase):
    def test_invalid_alias_name(self):
        json_dict = {
            "sets":
            [
                {
                    "primary": "https://primary.com",
                    "ccTLDs": {
                        "https://primary.com": ["https://primary2.ca"]
                    }
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                     etlds=None,
                     icanns=set(["ca"]))
        loaded_sets = fp.load_sets()
        fp.find_invalid_alias_eSLDs(loaded_sets)
        self.assertEqual(fp.error_list, ["The following top level domain " + 
        "must match: https://primary.com, but is instead: "+
        "https://primary2.ca"])
                
    def test_invalid_alias_ccTLD(self):
        json_dict = {
            "sets":
            [
                {
                    "primary": "https://primary.com",
                    "ccTLDs": {
                        "https://primary.com": ["https://primary.gov"]
                    }
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                     etlds=None,
                     icanns=set(["ca"]))
        loaded_sets = fp.load_sets()
        fp.find_invalid_alias_eSLDs(loaded_sets)
        self.assertEqual(fp.error_list, ["The provided country code: gov, "+
            "in: https://primary.gov is not a ICANN registered country code"])
                
    def test_invalid_com_in_alias(self):
        json_dict = {
            "sets":
            [
                {
                    "primary": "https://primary.edu",
                    "ccTLDs": {
                        "https://primary.edu": ["https://primary.com"]
                    }
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                     etlds=None,
                     icanns=set(["ca"]))
        loaded_sets = fp.load_sets()
        fp.find_invalid_alias_eSLDs(loaded_sets)
        self.assertEqual(fp.error_list, ["The provided country code: com, "+
            "in: https://primary.com is not a ICANN registered country code"])
                
    def test_valid_com_in_alias(self):
        json_dict = {
            "sets":
            [
                {
                    "primary": "https://primary.ca",
                    "ccTLDs": {
                        "https://primary.ca": ["https://primary.com"]
                    }
                },
                {
                    "primary": "https://primary2.co.uk",
                    "ccTLDs": {
                        "https://primary2.co.uk": ["https://primary2.com"]
                    }
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                     etlds=None,
                     icanns=set(["ca", "uk"]))
        loaded_sets = fp.load_sets()
        fp.find_invalid_alias_eSLDs(loaded_sets)
        self.assertEqual(fp.error_list, [])
    
    def test_invalid_associated_alias(self):
        json_dict = {
            "sets":
            [
                {
                    "primary": "https://primary.com",
                    "associatedSites": ["https://associated.com"],
                    "ccTLDs": {
                        "https://associated.com": ["https://associated.gov"]
                    }
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                     etlds=None,
                     icanns=set(["ca"]))
        loaded_sets = fp.load_sets()
        fp.find_invalid_alias_eSLDs(loaded_sets)
        self.assertEqual(fp.error_list, ["The provided country code: gov, "+
            "in: https://associated.gov is not a ICANN registered country code"])
        
    def test_valid_associated_alias(self):
        json_dict = {
            "sets":
            [
                {
                    "primary": "https://primary.com",
                    "associatedSites": ["https://associated.com"],
                    "ccTLDs": {
                        "https://associated.com": ["https://associated.ca"]
                    }
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                     etlds=None,
                     icanns=set(["ca"]))
        loaded_sets = fp.load_sets()
        fp.find_invalid_alias_eSLDs(loaded_sets)
        self.assertEqual(fp.error_list, [])
    
    def test_expected_esld(self):
        json_dict = {
            "sets":
            [
                {
                    "primary": "https://primary.com",
                    "ccTLDs": {
                        "https://primary.com": ["https://primary.ca"]
                    }
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                     etlds=None,
                     icanns=set(["ca"]))
        loaded_sets = fp.load_sets()
        fp.find_invalid_alias_eSLDs(loaded_sets)
        self.assertEqual(fp.error_list, [])

class TestFindDiff(unittest.TestCase):
    def test_unchanged_sets(self):
        old_sets = {
            'https://primary.com': 
            FpsSet(
                    primary="https://primary.com",
                    ccTLDs={
                        "https://primary.com": ["https://primary.ca"]
                    }
                    )
        }
        new_sets = {
            'https://primary.com': 
            FpsSet(
                    primary="https://primary.com",
                    ccTLDs={
                        "https://primary.com": ["https://primary.ca"]
                    }
                    )
        }
        self.assertEqual(find_diff_sets(old_sets, new_sets), ({},{}))

    def test_added_set(self):
        old_sets = {
            'https://primary.com': 
            FpsSet(
                    primary="https://primary.com",
                    ccTLDs={
                        "https://primary.com": ["https://primary.ca"]
                    }
                    )
        }
        new_sets = {
            'https://primary.com': 
            FpsSet(
                    primary="https://primary.com",
                    ccTLDs={
                        "https://primary.com": ["https://primary.ca"]
                    }
                    ),
            'https://primary2.com': 
            FpsSet(
                    primary="https://primary2.com",
                    ccTLDs={
                        "https://primary2.com": ["https://primary2.ca"]
                    }
                    )
        }
        expected_diff_sets = {
            'https://primary2.com': 
            FpsSet(
                    primary="https://primary2.com",
                    ccTLDs={
                        "https://primary2.com": ["https://primary2.ca"]
                    }
                    )
        }
        self.assertEqual(find_diff_sets(old_sets, new_sets), (expected_diff_sets,{}))
                
    def test_removed_set(self):
        old_sets = {
            'https://primary.com': 
            FpsSet(
                    primary="https://primary.com",
                    ccTLDs={
                        "https://primary.com": ["https://primary.ca"]
                    }
                    ),
            'https://primary2.com': 
            FpsSet(
                    primary="https://primary2.com",
                    ccTLDs={
                        "https://primary2.com": ["https://primary2.ca"]
                    }
                    )
        }
        new_sets = {
            'https://primary.com': 
            FpsSet(
                    primary="https://primary.com",
                    ccTLDs={
                        "https://primary.com": ["https://primary.ca"]
                    }
                    )
        }
        expected_subtracted_sets = {
            'https://primary2.com': 
            FpsSet(
                    primary="https://primary2.com",
                    ccTLDs={
                        "https://primary2.com": ["https://primary2.ca"]
                    }
                    )
        }
        self.assertEqual(find_diff_sets(old_sets, new_sets), ({},expected_subtracted_sets))
                
    def test_added_and_removed_set(self):
        old_sets = {
            'https://primary.com': 
            FpsSet(
                    primary="https://primary.com",
                    ccTLDs={
                        "https://primary.com": ["https://primary.ca"]
                    }
                    )
        }
        new_sets = {
            'https://primary2.com': 
            FpsSet(
                    primary="https://primary2.com",
                    ccTLDs={
                        "https://primary2.com": ["https://primary2.ca"]
                    }
                    )
        }
        self.assertEqual(find_diff_sets(old_sets, new_sets),(new_sets, old_sets))
                
    def test_modified_set(self):
        old_sets = {
            'https://primary.com': 
            FpsSet(
                    primary="https://primary.com",
                    ccTLDs={
                        "https://primary.com": ["https://primary.ca"]
                    }
                    )
        }
        new_sets = {
            'https://primary.com': 
            FpsSet(
                    primary="https://primary.com",
                    ccTLDs={
                        "https://primary.com": ["https://primary.co.uk"]
                    }
                    )
        }
        self.assertEqual(find_diff_sets(old_sets, new_sets), (new_sets, {}))

    def test_primary_to_member(self):
        old_sets = {
            'https://primary.com': 
            FpsSet(
                    primary="https://primary.com",
                    ccTLDs={
                        "https://primary.com": ["https://primary.ca"]
                    }
                    ),
            'https://primary2.com':
            FpsSet(
                    primary="https://primary2.com",
                    ccTLDs={
                    }
                    )
        }
        new_sets = {
            'https://primary.com': 
            FpsSet(
                    primary="https://primary.com",
                    associated_sites= ["https://primary2.com"],
                    ccTLDs={
                        "https://primary.com": ["https://primary.ca"]
                    }
                    )
        }
        self.assertEqual(find_diff_sets(old_sets, new_sets), (new_sets, {}))


# This method will be used in tests below to mock get requests
def mock_get(*args, **kwargs):
    class MockedGetResponse:
        def __init__(self, headers, status_code):
            self.headers = structures.CaseInsensitiveDict(headers)
            self.status_code = status_code
            self.url = args[0]

    if args[0] == 'https://service1.com':
        return MockedGetResponse({}, 200)
    elif args[0] == 'https://service2.com':
        return MockedGetResponse({"X-Robots-Tag":"foo"}, 200)
    elif args[0] == 'https://service3.com':
        return MockedGetResponse({"X-Robots-Tag":"noindex"}, 200)
    elif args[0] == 'https://service4.com':
        return MockedGetResponse({"X-Robots-Tag":"none"}, 200)
    elif args[0] == 'https://service5.com/ads.txt':
        return MockedGetResponse({}, 400)
    elif args[0] == 'https://service6.com':
        mgr = MockedGetResponse({}, 200)
        mgr.url = 'https://example.com'
        return mgr
    elif args[0].startswith('https://service'):
        return MockedGetResponse({},200)
    elif args[0] == 'https://primary1.com/.well-known/first-party-set.json':
        return MockedGetResponse({}, 200)
    
    return MockedGetResponse(None, 404)

def mock_open_and_load_json(*args, **kwargs):
    class MockedJsonResponse:
        def __init__(self, json):
            self.json = json
    
    if args[0] == 'https://primary1.com/.well-known/first-party-set.json':
        return {
            "primary": "https://primary1.com",
            "associatedSites": ["https://not-in-list.com"]
        }
    elif args[0] == 'https://expected-associated.com/.well-known/first-party-set.json':
        return {
            "primary": "https://primary1.com"
        }
    elif args[0] == 'https://primary2.com/.well-known/first-party-set.json':
        return {
            "primary": "https://wrong-primary.com",
            "associatedSites":["https://associated1.com"]
        }
    elif args[0] == 'https://associated1.com/.well-known/first-party-set.json':
        return {
            "primary": "https://primary2.com"
        }
    elif args[0] == 'https://primary3.com/.well-known/first-party-set.json':
        return {
            "primary": "https://primary3.com",
            "associatedSites": ["https://associated2.com"]
        }
    elif args[0] == 'https://associated2.com/.well-known/first-party-set.json':
        return {
            "primary": "https://wrong-primary.com"
        }
    elif args[0] == 'https://primary4.com/.well-known/first-party-set.json':
        return {
            "primary": "https://primary4.com",
            "associatedSites": ["https://associated3.com"]
        }
    elif args[0] == 'https://associated3.com/.well-known/first-party-set.json':
        return {
            "primary": "https://primary4.com"
        }
    return {"primary":None}

# Our test case class
class MockTestsClass(unittest.TestCase):

    # We patch requests.get with our mocked method. We'll pass
    # in the relevant urls, and get our responses for robots checks
    @mock.patch('requests.get', side_effect=mock_get)
    def test_robots(self, mock_get):
        # Assert requests.get calls
        json_dict = {
            "sets":
            [
                {
                    "primary": "https://primary.com",
                    "serviceSites": ["https://service1.com"]
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                     etlds=None,
                     icanns=set())
        loaded_sets = fp.load_sets()
        fp.find_robots_txt(loaded_sets)
        self.assertEqual(fp.error_list, ["The service site " +
        "https://service1.com " +
        "does not have an X-Robots-Tag in its header"])
        
    @mock.patch('requests.get', side_effect=mock_get)
    def test_robots_wrong_tag(self, mock_get):
        # Assert requests.get calls
        json_dict = {
            "sets":
            [
                {
                    "primary": "https://primary.com",
                    "serviceSites": ["https://service2.com"]
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                     etlds=None,
                     icanns=set())
        loaded_sets = fp.load_sets()
        fp.find_robots_txt(loaded_sets)
        self.assertEqual(fp.error_list, ["The service site " +
        "https://service2.com " +
        "does not have a 'noindex' or 'none' tag in its header"])

    @mock.patch('requests.get', side_effect=mock_get)
    def test_robots_expected_tag(self, mock_get):
        # Assert requests.get calls
        json_dict = {
            "sets":
            [
                {
                    "primary": "https://primary.com",
                    "serviceSites": ["https://service3.com"]
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                     etlds=None,
                     icanns=set())
        loaded_sets = fp.load_sets()
        fp.find_robots_txt(loaded_sets)
        self.assertEqual(fp.error_list, [])

    @mock.patch('requests.get', side_effect=mock_get)
    def test_robots_none_tag(self, mock_get):
        # Assert requests.get calls
        json_dict = {
            "sets":
            [
                {
                    "primary": "https://primary.com",
                    "serviceSites": ["https://service4.com"]
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                     etlds=None,
                     icanns=set())
        loaded_sets = fp.load_sets()
        fp.find_robots_txt(loaded_sets)
        self.assertEqual(fp.error_list, [])

    # We run a similar set of mock tests for ads.txt
    @mock.patch('requests.get', side_effect=mock_get)
    def test_ads(self, mock_get):
        # Assert requests.get calls
        json_dict = {
            "sets":
            [
                {
                    "primary": "https://primary.com",
                    "serviceSites": ["https://service1.com"]
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                     etlds=None,
                     icanns=set())
        loaded_sets = fp.load_sets()
        fp.find_ads_txt(loaded_sets)
        self.assertEqual(fp.error_list, ["The service site " +
        "https://service1.com has an ads.txt file, this " +
        "violates the policies for service sites"])

    @mock.patch('requests.get', side_effect=mock_get)
    def test_ads(self, mock_get):
        # Assert requests.get calls
        json_dict = {
            "sets":
            [
                {
                    "primary": "https://primary.com",
                    "serviceSites": ["https://service5.com"]
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                     etlds=None,
                     icanns=set())
        loaded_sets = fp.load_sets()
        fp.find_ads_txt(loaded_sets)
        self.assertEqual(fp.error_list, [])

    # We run a similar set of mock tests for redirect check
    @mock.patch('requests.get', side_effect=mock_get)
    def test_non_redirect(self, mock_get):
        # Assert requests.get calls
        json_dict = {
            "sets":
            [
                {
                    "primary": "https://primary.com",
                    "serviceSites": ["https://service1.com"]
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                     etlds=None,
                     icanns=set())
        loaded_sets = fp.load_sets()
        fp.check_for_service_redirect(loaded_sets)
        self.assertEqual(fp.error_list, ["The service site " +
        "must not be an endpoint: https://service1.com"])

    @mock.patch('requests.get', side_effect=mock_get)
    def test_proper_redirect(self, mock_get):
        # Assert requests.get calls
        json_dict = {
            "sets":
            [
                {
                    "primary": "https://primary.com",
                    "serviceSites": ["https://service6.com"]
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                     etlds=None,
                     icanns=set())
        loaded_sets = fp.load_sets()
        fp.check_for_service_redirect(loaded_sets)
        self.assertEqual(fp.error_list, [])

    @mock.patch('requests.get', side_effect=mock_get)
    def test_404_redirect(self, mock_get):
        # Assert requests.get calls
        json_dict = {
            "sets":
            [
                {
                    "primary": "https://primary.com",
                    "serviceSites": ["https://no-such-service.com"]
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                     etlds=None,
                     icanns=set())
        loaded_sets = fp.load_sets()
        fp.check_for_service_redirect(loaded_sets)
        self.assertEqual(fp.error_list, [])

    # Now we test check_invalid_removal by checking for an error 404
    @mock.patch('requests.get', side_effect=mock_get)
    def test_find_invalid_removal(self, mock_get):
        subtracted_sets = {
            'https://primary1.com': 
            FpsSet(
                    primary='https://primary1.com',
                    ccTLDs={}
                    )
        }
        fp = FpsCheck(fps_sites={},
                     etlds=None,
                     icanns=set())
        fp.find_invalid_removal(subtracted_sets)
        self.assertEqual(fp.error_list, ["The set associated with " +
                "https://primary1.com was removed from the list, but " +
                "https://primary1.com/.well-known/first-party-set.json does " +
                "not return error 404."])
        
    @mock.patch('requests.get', side_effect=mock_get)
    def test_find_valid_removal(self, mock_get):
        subtracted_sets = {
            'https://primary2.com': 
            FpsSet(
                    primary="https://primary2.com",
                    ccTLDs={}
                    )
        }
        fp = FpsCheck(fps_sites={},
                     etlds=None,
                     icanns=set())
        fp.find_invalid_removal(subtracted_sets)
        self.assertEqual(fp.error_list, [])

    # Now we test the mocked open_and_load_json to test the well-known checks
    @mock.patch('FpsCheck.FpsCheck.open_and_load_json', 
    side_effect=mock_open_and_load_json)
    def test_primary_page_differs(self, mock_open_and_load_json):
        json_dict = {
            "sets":
            [
                {
                    "primary": "https://primary1.com",
                    "associatedSites": ["https://expected-associated.com"]
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                     etlds=None,
                     icanns=set())
        loaded_sets = fp.load_sets()
        fp.find_invalid_well_known(loaded_sets)
        self.assertEqual(fp.error_list, ["The following member(s) of " +
        "associatedSites were not present in both the changelist and " + 
        ".well-known/first-party-set.json file: ['https://expected-associated.com'"
        + ", 'https://not-in-list.com']"])
    
    @mock.patch('FpsCheck.FpsCheck.open_and_load_json', 
    side_effect=mock_open_and_load_json)
    def test_wrong_primary_name(self, mock_open_and_load_json):
        json_dict = {
            "sets":
            [
                {
                    "primary": "https://primary2.com",
                    "associatedSites": ["https://associated1.com"]
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                     etlds=None,
                     icanns=set())
        loaded_sets = fp.load_sets()
        fp.find_invalid_well_known(loaded_sets)
        self.assertEqual(fp.error_list, ["The following member(s) of " +
        "primary were not present in both the changelist and " + 
        ".well-known/first-party-set.json file: ['https://primary2.com'"
        + ", 'https://wrong-primary.com']"])

    @mock.patch('FpsCheck.FpsCheck.open_and_load_json', 
    side_effect=mock_open_and_load_json)
    def test_associate_wrong_page(self, mock_open_and_load_json):
        json_dict = {
            "sets":
            [
                {
                    "primary": "https://primary3.com",
                    "associatedSites": ["https://associated2.com"]
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                     etlds=None,
                     icanns=set())
        loaded_sets = fp.load_sets()
        fp.find_invalid_well_known(loaded_sets)
        self.assertEqual(fp.error_list, ["The listed associated site "
                + "did not have https://primary3.com listed as its primary: " 
                + "https://associated2.com"])

    @mock.patch('FpsCheck.FpsCheck.open_and_load_json', 
    side_effect=mock_open_and_load_json)
    def test_expected_case(self, mock_open_and_load_json):
        json_dict = {
            "sets":
            [
                {
                    "primary": "https://primary4.com",
                    "associatedSites": ["https://associated3.com"]
                }
            ]
        }
        fp = FpsCheck(fps_sites=json_dict,
                     etlds=None,
                     icanns=set())
        loaded_sets = fp.load_sets()
        fp.find_invalid_well_known(loaded_sets)
        self.assertEqual(fp.error_list, [])

if __name__ == '__main__':
    unittest.main()
