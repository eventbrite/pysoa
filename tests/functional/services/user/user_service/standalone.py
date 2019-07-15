
from pysoa.server.standalone import django_main


def main():
    def gs():
        from user_service.server import Server
        return Server
    django_main(gs)


if __name__ == '__main__':
    main()
