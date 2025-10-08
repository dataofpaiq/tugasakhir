def flow_training(self):
    self.logger.info("Flow Training ...")

    try:
        flow_dataset = pd.read_csv('FlowStatsfile.csv')
        if flow_dataset.empty:
            raise ValueError("Dataset kosong!")

        self.logger.info(f"Dataset shape: {flow_dataset.shape}")
        self.logger.info(flow_dataset.head())

        # Fix penghapusan titik (gunakan regex=False)
        flow_dataset.iloc[:, 2] = flow_dataset.iloc[:, 2].str.replace('.', '', regex=False)
        flow_dataset.iloc[:, 3] = flow_dataset.iloc[:, 3].str.replace('.', '', regex=False)
        flow_dataset.iloc[:, 5] = flow_dataset.iloc[:, 5].str.replace('.', '', regex=False)

        X_flow = flow_dataset.iloc[:, :-1].values
        X_flow = X_flow.astype('float64')

        y_flow = flow_dataset.iloc[:, -1].values

        if len(X_flow) == 0 or len(y_flow) == 0:
            raise ValueError("Dataset tidak memiliki cukup data untuk training.")

        X_flow_train, X_flow_test, y_flow_train, y_flow_test = train_test_split(
            X_flow, y_flow, test_size=0.25, random_state=0)

        classifier = RandomForestClassifier(n_estimators=10, criterion="entropy", random_state=0)
        self.flow_model = classifier.fit(X_flow_train, y_flow_train)

        y_flow_pred = self.flow_model.predict(X_flow_test)

        cm = confusion_matrix(y_flow_test, y_flow_pred)
        acc = accuracy_score(y_flow_test, y_flow_pred)

        self.logger.info("------------------------------------------------------------------------------")
        self.logger.info("confusion matrix")
        self.logger.info(cm)
        self.logger.info("succes accuracy = {0:.2f} %".format(acc*100))
        self.logger.info("fail accuracy = {0:.2f} %".format((1.0 - acc)*100))
        self.logger.info("------------------------------------------------------------------------------")

    except Exception as e:
        self.logger.error(f"[ERROR] Gagal saat training: {e}")
