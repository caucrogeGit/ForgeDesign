raise AssertionError("module executed")
from mvc.controllers.contact_controller import ContactController
from mvc.controllers.missing_controller import MissingController
from mvc.controllers.pivot.contact import PivotController
def register_contact_routes(router):
    with router.group("/contact", public=True) as public:
        public.add("GET", "/list", ContactController.list)
    router.add("POST", "/contact/create", ContactController.create)
