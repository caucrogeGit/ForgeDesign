raise AssertionError("controller executed")
class ContactController:
    def list(self): return BaseController.render("contacts/list.html")
    def create(self): return BaseController.render("contacts/create.html")
    def invalid(self): return BaseController.render("invalid.html")
    def absent(self): return BaseController.render("missing.html")
