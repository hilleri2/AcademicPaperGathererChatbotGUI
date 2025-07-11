import requests
import random
from fp.fp import FreeProxy


class Proxies:
    proxy_list = None

    def get_free_proxies(self):
        proxies = []
        # Proxies gathered are a subset of the proxies available at https://github.com/proxifly/free-proxy-list
        # Proxifly allows for the free use of these proxies, assuming standard use practices are adhered to
        url = "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/countries/US/data.json"
        content = requests.get(url).json()
        for item in content:
            if item['protocol'] == "http":
                proxies.append(item['proxy'])
        return proxies

    def validate_proxies(self, test_url="https://httpbin.org/ip"):  # This URL doesn't work?
        print("[*] Validating proxies...")
        valid = []
        for proxy in self.proxy_list:
            try:
                r = requests.get(test_url, proxies={"http": proxy, "https": proxy}, timeout=5)
                if r.status_code == 200:
                    valid.append(proxy)
                    # print(f"[✓] Valid proxy: {proxy}")
            except:
                pass
                # print(f"[✗] Invalid proxy: {proxy}")
        print(f"[+] {len(valid)} proxies validated.")
        return valid

    def get_proxy(self):
        return FreeProxy(country_id=['US']).get()

    def get_rand_proxy(self):
        if self.proxy_list is None:
            self.proxy_list = self.get_free_proxies()
            # self.proxy_list = self.validate_proxies()
        selected_proxy = random.choice(self.proxy_list)
        return {"http": selected_proxy, "https": selected_proxy}
