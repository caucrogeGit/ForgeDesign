
raise AssertionError("controller executed")
class HomeController(BaseController):
    @staticmethod
    def index(request):
        return BaseController.render("home/index.html", request=request)
    @staticmethod
    def charte(request):
        return BaseController.render("pages/charte.html", request=request)
