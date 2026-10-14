from mvc.controllers.user_controller import UserController
def register_user_routes(router):
    router.add("GET", "/users", UserController.index)
    router.add("GET", "/factory", factory())
