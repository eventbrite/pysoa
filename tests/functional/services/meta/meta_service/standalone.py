from pysoa.server.standalone import simple_main


def main():
    from meta_service.server import Server
    simple_main(lambda: Server)


if __name__ == '__main__':
    main()
