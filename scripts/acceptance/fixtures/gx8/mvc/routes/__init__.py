from core.http.router import Router
from mvc.controllers.home_controller import HomeController
from optins.registry import register_optins
router = Router()
with router.group("", public=True) as public:
    public.add("GET", "/", HomeController.index, name="home-index")
    public.add("GET", "/charte", HomeController.charte, name="home-charte")
register_optins(router)
raise AssertionError("routes executed")
from mvc.routes.contact_routes import register_contact_routes
from mvc.routes.user_routes import register_user_routes
register_contact_routes(router)
register_user_routes(router)
