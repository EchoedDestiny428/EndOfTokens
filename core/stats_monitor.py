class StatsMonitor:
    def __init__(self):
        self.total_requests = 0
        self.pro_requests = 0
        self.free_requests = 0
        self.double_checks = 0
        self.total_response_time = 0.0
        
    def add_request(self, mode: str, response_time: float, double_checked: bool = False):
        self.total_requests += 1
        self.total_response_time += response_time
        if mode == "pro":
            self.pro_requests += 1
        elif mode == "free":
            self.free_requests += 1
            
        if double_checked:
            self.double_checks += 1
            
    def get_avg_response_time(self):
        if self.total_requests == 0:
            return 0.0
        return self.total_response_time / self.total_requests
        
    def get_stats(self):
        return {
            "Total Requests": self.total_requests,
            "Pro Mode Uses": self.pro_requests,
            "Free Mode Uses": self.free_requests,
            "Double Checks Performed": self.double_checks,
            "Avg Response Time (s)": round(self.get_avg_response_time(), 2)
        }

# Singleton instance
stats_monitor = StatsMonitor()
