import matplotlib

def main():
    matplotlib.use('Qt4Agg')
    from nexpy.gui.consoleapp import NXConsoleApp
    app = NXConsoleApp()
    app.initialize()
    app.start()


if __name__ == '__main__':
    main()
